# SKILLS.md — realpath.dev Playbook'ları ve Claude Code Skill'leri

> Amaç: tekrar eden işleri **bir daha sıfırdan keşfetmemek**. Bir görevi nasıl yaptığımızı bir kez yaz, her session'da aynı reçeteyi izle.
>
> realpath.dev — açık kaynak, self-hostable, **local-first** relational prediction engine. Bir veritabanı bağla, tahmine dayalı bir soruyu düz dille veya PQL ile sor, **açıklamalı** (explained) bir cevap al — veriyi hiçbir yere taşımadan. Kumo.AI / KumoRFM'in açık kaynak karşılığı.

## Altın Kurallar (her session geçerli — ASLA ihlal etme)

1. **`pushla` / "push" denmeden remote'a PUSH YOK.** PR açma, merge yok. Lokal commit serbest, ama iş bitiminde topluca atılır (her küçük adımda değil), sonra dur ve bekle.
2. **Commit kimliği global gitconfig'ten gelir** (author `Özgür Işık Damar`, GitHub no-reply email). `Co-Authored-By: Claude` veya herhangi bir Claude trailer/imza **ASLA** eklenmez. Mesajlar kısa, insanca, **İngilizce**.
3. **pandas 2.2.x'e pinli kalır** (2.2.3). pandas 3.0 woodwork'ü bozar (`.ww` accessor şeması persist etmez) → EntitySet build çöker. **Yükseltme.**
4. **Core bağımlılıklar permissive lisanslı kalır** (MIT/BSD/Apache). getML (ELv2) ve TabPFN-2.5 (non-commercial) **karantinada** — yalnızca optional/plugin, asla core dependency.
5. **NL→PQL için Claude yolu `ANTHROPIC_API_KEY` ister**; yoksa offline template fallback kullanılır. Varsayılan model `claude-sonnet-4-6` (env `REALPATH_LLM_MODEL` ile override).
6. **Local-first ürün tezidir**: veri makineden çıkmak zorunda olmamalı. DuckDB varsayılan kalır.
7. **Windows'ta `PYTHONUTF8=1`** tercih et (veya `realpath._io.sprint`'e güven) ki Türkçe metin cp1252 console'da çökmesin.

### Ortam (environment) hızlı referansı

| Şey | Değer |
|---|---|
| Repo kökü | `C:\Users\isiko\OneDrive\Desktop\AI Projects\realpath` |
| Python | 3.11, virtualenv `.venv` (`.venv\Scripts\python.exe`) |
| Editable install | `.venv\Scripts\python.exe -m pip install -e .` (entry point script: `realpath`) |
| Kurulu extralar | core + `anthropic` + `shap` + `streamlit` + `pytest` |
| Kurulu DEĞİL | `relbench` / `torch` (eval extra) |
| Örnek DB | `data/shop.duckdb` (gitignored — yeniden üret) |
| UTF-8 | `$env:PYTHONUTF8 = "1"` (PowerShell) |

---

# PART A — PROJE PLAYBOOK'LARI (recipes)

Her reçete: **Amaç → Adımlar → Dosyalar → Doğrulama**.

---

## A1. Yeni dikey şablon (vertical template) ekle

**Amaç:** Bir domain problemini (churn/forecast/fraud gibi) tek-satırlık bir komuta indir, kullanıcı boş sayfadan başlamasın.

**Adımlar:**

1. `realpath/templates.py` içinde `TEMPLATES` registry'sine yeni bir giriş ekle (`desc` + `params`). Mevcutlar: `churn`, `forecast`, `fraud`.
2. Aynı dosyada bir **PQL builder** fonksiyonu yaz — mevcutlar PQL string döndürüyor:
   - `churn_pql(entity, key, event, horizon_days=30)` → `PREDICT COUNT(<event>.*, 0, <h>, days) == 0 FOR EACH <entity>.<key>`
   - `forecast_pql(entity, key, event, column, horizon_months=3)` → `PREDICT SUM(<event>.<column>, 0, <h>, months) FOR EACH <entity>.<key>`
   - `fraud_pql(entity, key, event, horizon_days=60, where=None)` → `PREDICT COUNT(<event>.*, 0, <h>, days) > 0 FOR EACH <entity>.<key> [ASSUMING <where>]`
3. `realpath/engine.py` içinde `Engine`'e bir metot ekle (mevcutlar: `churn()`, `forecast()`, `fraud()`). Metot builder'ı çağırıp `self.predict(...)` ile çalıştırmalı.
4. `tests/` altına bir test ekle: builder'ın ürettiği PQL'i `parse_pql` ile parse et ve `PredictiveTask`'ın doğru olduğunu doğrula (gerekirse `sample_db` fixture ile uçtan uca koştur).

**Dosyalar:** `realpath/templates.py`, `realpath/engine.py`, `tests/test_pql_parser.py` (veya yeni test dosyası), `tests/conftest.py` (`sample_db` fixture).

**Doğrulama:**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
# ve uçtan uca:
.venv\Scripts\python.exe -m realpath.cli predict "<builder'ın ürettiği PQL>" --db data/shop.duckdb --explain
```

---

## A2. Yeni DB connector ekle

**Amaç:** DuckDB dışında bir kaynağı (Postgres/MySQL) aynı arayüzün arkasına koy — local-first tezini bozmadan.

**Bağlam:** Şu an yalnızca DuckDB var. `connect.py` içindeki `open_backend()`, `://` içeren URL'lerde net bir `NotImplementedError` fırlatır (Phase-2 roadmap).

**Adımlar:**

1. `realpath/connect.py` içinde `DuckDBBackend` arayüzünü birebir uygulayan yeni bir backend sınıfı yaz. Sağlanması gereken yüzey:

   | Metot | İmza / dönüş |
   |---|---|
   | `tables()` | `list[str]` |
   | `columns(table)` | `list[ColumnInfo]` (`name`, `sql_type`) |
   | `row_count(table)` | `int` |
   | `distinct_count(table, column)` | `tuple[int, int]` → `(n_non_null, n_distinct)` |
   | `load(table)` | `pd.DataFrame` |
   | `query(sql, params=None)` | `pd.DataFrame` |
   | `close()` | `None` |

2. `open_backend(source)` içine yönlendirmeyi bağla. Şu an: `:memory:` veya `.duckdb/.db/.ddb` uzantısı → DuckDB; `://` içeren URL → `NotImplementedError`. Yeni connector için ilgili scheme'i (`postgres://`, `mysql://`) yakala ve yeni backend'i döndür.
3. `schema.py` / `features.py` ham SQL tipine değil pandas çıktısına dayanır; yine de `_normalize_dtypes()` (schema.py) DuckDB çıktısını `datetime64[ns]`/`object`'e coerce ettiği için yeni backend de **woodwork-uyumlu** dtype'lar döndürmeli (datetime + object), yoksa EntitySet build çöker.
4. Lisansı kontrol et: yeni driver permissive (MIT/BSD/Apache) olmalı.

**Dosyalar:** `realpath/connect.py` (ana iş), `realpath/schema.py` (dtype normalize uyumu), `tests/` (yeni connector için bir smoke test).

**Doğrulama:**

```powershell
# DuckDB regresyona uğramamalı:
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m realpath.cli schema --db data/shop.duckdb
```

> **Not:** Local-first kuralı — bir Postgres backend eklesen bile veriyi makineden çıkarma. DuckDB'nin `ATTACH` yeteneği ile Postgres'i DuckDB'ye bağlamak da geçerli bir yol (`open_backend` hata mesajı bunu öneriyor).

---

## A3. Yeni PQL agregasyonu ekle

**Amaç:** PQL grameri yeni bir `AGG`'i desteklesin (mevcutlar: `COUNT, SUM, AVG, MIN, MAX`; `MEAN` → `AVG` alias).

**Hatırlatma — PQL grameri:**

```
PREDICT AGG(table.col|*, start, end, unit) [op value]
FOR EACH entity_table.primary_key
[WHERE filter] [ASSUMING filter]
```
`unit ∈ {days, weeks, months}`, `op ∈ {==, !=, >, >=, <, <=}`. Comparison varsa **classification**, yoksa **regression**.

**Adımlar:**

1. `realpath/pql/ast.py` → `AGGS` setine yeni fonksiyonu ekle (gerekirse alias'ı parser'da çöz, `MEAN→AVG` gibi).
2. `realpath/pql/parser.py` → `_parse_target()` mantığını gözden geçir. Regex (`_AGG_RE`) zaten `[A-Za-z_]+` func adını yakalar; `func not in AGGS` kontrolü yeni aggi otomatik kabul eder. `func != "COUNT" and col is None` kuralına dikkat (yeni agg `*` ile çalışmıyorsa column zorunluluğunu koru).
3. `realpath/pql/compile.py` → SQL mapping'i ekle. Label/event CTE'lerinde bu aggregate'i üreten SQL'i ve regression/classification eşlemesini güncelle (`build_split` events CTE + COALESCE).
4. `tests/test_pql_parser.py` → yeni agg için en az bir geçerli ve gerekirse bir geçersiz (`PQLSyntaxError`) case ekle.

**Dosyalar:** `realpath/pql/ast.py`, `realpath/pql/parser.py`, `realpath/pql/compile.py`, `tests/test_pql_parser.py`.

**Doğrulama:**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_pql_parser.py -q
.venv\Scripts\python.exe -m realpath.cli predict "PREDICT <YENI_AGG>(transactions.amount, 0, 30, days) FOR EACH customers.customer_id" --db data/shop.duckdb
```

---

## A4. Örnek veritabanını yeniden üret

**Amaç:** Gitignore'lu `data/shop.duckdb`'yi (deterministik, seed 42) yeniden oluştur.

**Adımlar:**

```powershell
.venv\Scripts\python.exe data\make_sample_db.py data\shop.duckdb
```

Üretir: sentetik e-ticaret DB, 4 tablo —
`customers(customer_id pk, signup_date, country, segment)`,
`products(product_id pk, category, brand, price)`,
`transactions(tx_id pk, customer_id fk, product_id fk, tx_time, quantity, amount)`,
`returns(return_id pk, tx_id fk, return_time, reason)`.
Seed 42, ~18 ay geçmiş, **~1200 customers, ~14343 transactions, ~2209 returns**. Churn öğrenilebilir; returns'te gizli per-customer propensity var → gelecekteki return-risk tahmin edilebilir.

**Dosyalar:** `data/make_sample_db.py` (CLI yolu: `realpath make-sample --out data/shop.duckdb`, ki `_cmd_make_sample` `build()`'i çağırır).

**Doğrulama:** Komutun çıktısı `Wrote data\shop.duckdb` ve satır sayılarını yazar. Ardından:

```powershell
.venv\Scripts\python.exe -m realpath.cli schema --db data\shop.duckdb
```
4 tabloyu ve çıkarılan FK graph'ını yazdırmalı.

---

## A5. Sızıntı (leakage) testini çalıştır ve yorumla

**Amaç:** Feature'ların gelecekteki bilgiyi sızdırmadığını ispatla — realpath'in temel doğruluk garantisi.

**Adımlar:**

```powershell
.venv\Scripts\python.exe -m pytest tests\test_leakage.py -q
```

**Test ne yapıyor:**
- Anchor'dan **sonraki tüm satırları siler** ve feature matrix'in **birebir aynı** kaldığını assert eder (cutoff-safe DFS kanıtı, `features.synthesize` `cutoff_time` ile çalışır).
- Label penceresinin **kesinlikle gelecekte** olduğunu kontrol eder (window `(anchor+start, anchor+end]`, yarı-açık).

**Dosyalar:** `tests/test_leakage.py`, `tests/conftest.py` (`sample_db` fixture, DB'yi geçici path'e kurar), `realpath/features.py` (`synthesize` + `cutoff_time`), `realpath/pql/compile.py` (`build_split` pencere SQL'i).

**Doğrulama / yorum:** Test geçerse, anchor sonrası satırların feature'ları etkilememesi = **no future leakage**. Test KIRILIRSA, önce `features.synthesize`'ın `cutoff_time`'ı ve `compile.build_split`'in pencere bounds'ını incele — sızıntı genelde DFS'in cutoff'u dikkate almamasından ya da pencerenin yanlışlıkla anchor'ı kapsamasından gelir.

---

## A6. Eval çalıştır (local) ve RelBench

**Amaç:** Relational feature'ların değerini ölç — realpath'in tam relational feature'ları ile relational-olmayan baseline'ı karşılaştır.

### A6.1 Yerel eval (extra GEREKMEZ)

```powershell
# tam relational vs no-relational baseline (entity'nin kendi kolonları):
.venv\Scripts\python.exe -m realpath.eval --db data\shop.duckdb
# veya belirli bir PQL ile:
.venv\Scripts\python.exe -m realpath.eval --db data\shop.duckdb --pql "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id"
```

`eval.evaluate_local(db, pql)` realpath'in full relational feature'larını entity-own-columns baseline'a karşı koşar.

**Beklenen (doğrulanmış metrikler, sample DB):**

| Görev | realpath | Baseline | Delta |
|---|---|---|---|
| Churn ROC-AUC | ~0.749 | ~0.704 | **+0.045** |
| Customer return-risk (2-hop join) ROC-AUC | ~0.689 | — | — |
| Product demand forecast (3 ay) MAE | ~8.4 | ~7.48 | iyileşme yok |

### A6.2 RelBench eval (önce `eval` extra'sını kur)

```powershell
.venv\Scripts\python.exe -m pip install -e ".[eval]"   # relbench + torch + torch-frame
.venv\Scripts\python.exe -m realpath.eval --dataset <relbench_dataset> --task <task>
```

> **Not:** RelBench yolu `eval` extra'sını (torch+relbench) ister ve **izole bir venv'de** kurulmalıdır
> (`.venv_eval`) ki çekirdek `.venv` bozulmasın. `relbench_adapter.run_relbench_task()` **rel-f1 ile
> doğrulandı** (driver-dnf AUC ~0.592, driver-position MAE ~3.61). İlk koşu dataset'i indirir →
> local-first değildir, yalnızca benchmark içindir.

**Dosyalar:** `realpath/eval.py` (`evaluate_local`, `evaluate_relbench`, `main()`), `realpath/relbench_adapter.py`, `realpath/cli.py` (`eval` subcommand), `pyproject.toml` (`[project.optional-dependencies] eval`).

**Doğrulama:** Local eval, realpath vs baseline metriklerini ve pozitif bir delta'yı yazdırmalı (churn için ~+0.045 civarı).

---

## A7. NL→PQL'i gerçek Claude ile çalıştır

**Amaç:** Düz dildeki soruyu LLM ile geçerli PQL'e çevir (offline template fallback yerine).

**Adımlar (PowerShell):**

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # zorunlu (Claude yolu için)
$env:REALPATH_LLM_MODEL  = "claude-sonnet-4-6"   # opsiyonel override (varsayılan zaten bu)
$env:PYTHONUTF8 = "1"
.venv\Scripts\python.exe -m realpath.cli ask "onumuzdeki ay churn edecek musteriler" --db data\shop.duckdb
```

**Nasıl çalışır:** `nlp.nl_to_pql(question, schema, model, max_retries)` Claude'u `anthropic` SDK ile çağırır, çıktıyı **yeniden parse ederek doğrular** (`parse_pql`), hata olursa parse hatasını geri besleyip retry yapar. `anthropic` yoksa veya `ANTHROPIC_API_KEY` yoksa **offline deterministik template matcher** devreye girer (churn/forecast/fraud keyword routing, Türkçe + İngilizce).

Çıktıdaki `source` alanı `claude` mı yoksa offline/template fallback mı kullanıldığını gösterir (`_cmd_ask` `[{nl.source}] {nl.pql}` basar).

**Dosyalar:** `realpath/nlp.py` (`nl_to_pql`, `NLResult`, `schema_summary`), `realpath/engine.py` (`ask()`), `realpath/cli.py` (`ask` subcommand).

**Doğrulama:** `[claude] PREDICT ...` ile başlayan, parse edilebilir bir PQL dönmeli. Anahtar yoksa `[template]`/offline source görürsün — yine de geçerli PQL.

---

## A8. Demo'yu başlat (Streamlit)

**Amaç:** Şemayı, NL/PQL girişini, template butonlarını, tahminleri, global importance grafiğini ve per-entity açıklama kartını tarayıcıda göster.

**Adımlar (PowerShell):**

```powershell
$env:PYTHONUTF8 = "1"
.venv\Scripts\streamlit.exe run realpath\demo_app.py
# veya:
.venv\Scripts\python.exe -m streamlit run realpath\demo_app.py
```

Varsayılan port **8501** → **http://localhost:8501**. UI Türkçe. Önce `data/shop.duckdb` üretilmiş olmalı (bkz. A4).

**Dosyalar:** `realpath/demo_app.py`, veri için `data/shop.duckdb`.

**Doğrulama:** Tarayıcıda şema görünür; bir template butonuna basınca tahminler + global importance chart + bir entity'nin join-path açıklama kartı gelir.

---

## A9. Spec dokümanını DOCX/HTML render et

**Amaç:** `docs/REALPATH_SPEC_v2.md`'yi DOCX ve HTML olarak üret; logoyu PNG'ye dönüştür.

**Bağlam (mevcut dosyalar):** `docs/REALPATH_SPEC_v2.md` + `.docx` + `.html`, ve `docs/logo.svg` + `docs/logo.png` zaten present.

**Adımlar:**

```powershell
# Markdown -> DOCX ve HTML (pandoc):
pandoc docs\REALPATH_SPEC_v2.md -o docs\REALPATH_SPEC_v2.docx
pandoc docs\REALPATH_SPEC_v2.md -s -o docs\REALPATH_SPEC_v2.html

# Logo SVG -> PNG (npm sharp ile):
npx sharp-cli -i docs\logo.svg -o docs\logo.png
```

> DOCX deliverable gerekiyorsa alternatif olarak `docx` skill'i (anthropic-skills) de kullanılabilir; ama mevcut çıktılar pandoc ile üretilmiştir, tutarlılık için pandoc tercih et.

**Dosyalar:** `docs/REALPATH_SPEC_v2.md` (kaynak), `docs/REALPATH_SPEC_v2.docx`, `docs/REALPATH_SPEC_v2.html`, `docs/logo.svg`, `docs/logo.png`.

**Doğrulama:** `docs/` altında `.docx` ve `.html` güncel zaman damgalı; PNG açılıyor ve şeffaf/temiz görünüyor.

---

## A10. Woodwork / pandas hatasını debug et

**Amaç:** En sık karşılaşılan altyapı hatasını — woodwork şemasının persist etmemesini — teşhis et ve çöz.

**Semptom:** Featuretools `EntitySet` build'i, `schema.py` içindeki `build_entityset()` çağrısında patlar; `.ww` accessor'a set edilen logical type'lar/şema **kaybolur** (persist etmez). Genelde sebebi: **pandas 3.0'a yükseltilmiş** olması.

**Kök neden:** pandas 3.0 woodwork ile uyumsuz — `.ww` accessor şeması persist olmaz, dolayısıyla EntitySet build başarısız olur.

**Çözüm:**

```powershell
.venv\Scripts\python.exe -c "import pandas; print(pandas.__version__)"   # 2.2.x olmalı
.venv\Scripts\python.exe -m pip install "pandas==2.2.3"
```

**Dosyalar:** `realpath/schema.py` (`build_entityset`, `_normalize_dtypes` — DuckDB çıktısını `datetime64[ns]`/`object`'e coerce eder ki woodwork kabul etsin), `pyproject.toml` (pin `pandas==2.2.3`).

**Doğrulama:**

```powershell
.venv\Scripts\python.exe -m pytest tests\ -q   # 25/25 geçmeli
```

> **Kural 3 hatırlatma:** pandas'ı **asla** 2.2.x üstüne çıkarma. Başka bir paket pandas 3.0 çekmek isterse onu pinle/iste, pandas'ı feda etme.

---

# PART B — İLGİLİ CLAUDE CODE SKILL / KOMUTLARI

Bu repo için pratik eşleme — ne zaman hangisi. (Tutorial değil; kısa rehber.)

| Skill / Komut | Ne zaman kullan (realpath bağlamı) |
|---|---|
| **`/code-review`** | Lokal commit'ten **önce** diff'i incele. Özellikle `pql/`, `compile.py`, `features.py` gibi sızıntı-hassas dosyalara dokunduğunda. Commit kuralı: iş bitiminde, topluca. |
| **`/verify`** | Bir fix'in gerçekten çalıştığını uygulamayı koşturarak doğrula — örn. yeni template (A1) veya connector (A2) sonrası uçtan uca `predict` davranışını gözlemle. |
| **`/run`** | Uygulamayı başlatıp bir değişikliği canlı görmek için — CLI (`realpath predict ...`) veya Streamlit demo (A8). Testten değil gerçek app'ten teyit. |
| **`deep-research`** | Rekabet/SOTA araştırması — Kumo.AI / KumoRFM, RelBench, relational deep learning literatürü. Konumlandırmayı veya roadmap'i güncellerken. |
| **`update-config`** | settings.json / permissions / hooks / env var değişiklikleri. Örn. `PYTHONUTF8=1`'i bir hook'a bağlamak veya `.venv` komutlarına permission allowlist eklemek. |
| **`ultracode` / Workflow** | Büyük, çok-adımlı işler (yeni connector + schema + features + test zinciri gibi A2-ölçeği görevler) için orchestration. |

**Genel akış hatırlatması:** araştır/planla → uygula → test (`pytest tests/ -q`) → `/code-review` ile diff'i gözden geçir → **iş bitince** lokal commit → dur, `pushla` onayını bekle.
