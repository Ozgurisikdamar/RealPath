# relpath.dev — Yol Haritası (ROADMAP)

> **Bu doküman stratejiktir.** Üç faza bölünmüş, gerekçeli bir backlog sunar.
> `docs/RELPATH_SPEC_v2.md` §9.2 yol haritası tablosunun açılımıdır ve onunla çelişmez.
>
> **ÖNEMLİ — bunun tersi HANDOVER:** *Şimdi-yap* (do-it-now) işler bu dosyada DEĞİL,
> `docs/HANDOVER.md` içindeki **"Sıradaki İş"** bölümünde tutulur. ROADMAP stratejik kalır,
> HANDOVER taktik. Bir item'a fiilen başlanacağında onu HANDOVER'a taşıyın.

**Tarih:** 2026-06-19 · **Sürüm:** relpath `0.1.0` · **Konum:** açık kaynak, self-hostable, **local-first** relational prediction engine — Kumo.AI / KumoRFM'in açık kaynak karşıtı.

---

## Efor / Bağımlılık Lejantı

| İşaret | Anlam |
|---|---|
| **S** | Küçük — birkaç saat / 1 gün |
| **M** | Orta — birkaç gün |
| **L** | Büyük — 1+ hafta, mimari dokunuş |

Bağımlılıklar "→" ile gösterilir (önce gelen → sonra gelen).

---

## Faz Özeti (tek bakış)

```
Faz 1 (BİTTİ — PoC)            Faz 2 (SIRADA — büyüme)        Faz 3 (VİZYON)
──────────────────────        ──────────────────────────     ──────────────────────
connect→PQL→DFS→LGBM           Postgres/MySQL konnektör       Warehouse read
NL→PQL (+offline fallback)     PyPI yayını + CI               (Snowflake/Databricks)
3 şablon (churn/forecast/      Daha çok dikey şablon          Relational Foundation
fraud)                         + testleri                     Model (in-context)
eval (local + relbench)        Canlı Claude NL→PQL            Streaming / real-time
12/12 test, sızıntı testi      RDL/GNN backend (relbench+PyG) Multimodal (metin sütun)
                               Kalibrasyon / belirsizlik      Managed / open-core
```

**Strateji (SPEC §4.1):** değerin %80'i Faz 1'de, maliyetin %20'siyle. GNN ve foundation-model
kanıtlanmış talep geldikçe eklenir — vitrin değil, yol haritası.

---

## Faz 1 — Local-First PoC ✅ (BİTTİ)

connect → PQL compile → DFS (cutoff-safe) → LightGBM/TabPFN → join-yolu açıklaması zinciri
çalışıyor. Bu faz teslim edildi; aşağısı kanıt amaçlı kontrol listesidir.

- [x] **DuckDB connector** — `connect.py` `DuckDBBackend` + `open_backend()`. (Postgres/MySQL URL'leri bilinçli olarak `NotImplementedError` → Faz 2.)
- [x] **Şema çıkarımı** — `schema.py` `infer_schema()`: PK / FK / time-index sezgileri, `join_path(a,b)` FK grafiği üzerinde BFS (multi-hop), `build_entityset()` Featuretools EntitySet.
- [x] **PQL** — `pql/` parser (regex gramer + WHERE/ASSUMING için sqlglot), AST, `compile.py` (join inference + temporal pencere izolasyonu, `default_anchors()`, `build_split()`).
- [x] **Sızıntı-güvenli öznitelik üretimi** — `features.py` `synthesize()`: `ft.dfs` + `cutoff_time`, AGG/TRANS primitives, pk/fk/text sütun eleme.
- [x] **Model** — `model.py` `fit_model()`: LightGBM (clf/reg), degenerate-target guard, opsiyonel TabPFN (auto, sadece kuruluysa).
- [x] **Açıklanabilirlik** — `explain.py`: join-yolu provenance, global gain importance, SHAP varsa entity kartı (`format_card()`).
- [x] **NL→PQL** — `nlp.py`: Claude (anthropic SDK) + re-parse doğrulama/retry; API yoksa **offline deterministik şablon fallback** (TR+EN).
- [x] **3 dikey şablon** — `templates.py` + `engine.py`: `churn()`, `forecast()`, `fraud()`.
- [x] **Eval** — `eval.py`: `evaluate_local()` (relational vs no-relational baseline) + `evaluate_relbench()` (eval extra ile).
- [x] **CLI + Demo** — `cli.py` (make-sample/schema/ask/predict/eval), `demo_app.py` (Streamlit).
- [x] **Testler** — `tests/`: 12/12 geçiyor; `test_leakage.py` anchor sonrası satırları silip feature matrix'in aynı kaldığını ispatlıyor.

**Doğrulanmış metrikler (sample DB):** churn ROC-AUC ~0.749 (entity-only baseline ~0.704, Δ +0.045); customer return-risk (2-hop join) ~0.689 ROC-AUC; product demand forecast (varsayılan 3 ay) MAE ~8.4 (ilişkisel lift yok; churn asıl gösterge).

```powershell
# Faz 1'i sıfırdan doğrula (Windows)
.venv\Scripts\python.exe -m pip install -e .
$env:PYTHONUTF8 = "1"
.venv\Scripts\python.exe data\make_sample_db.py data\shop.duckdb
.venv\Scripts\python.exe -m pytest tests\ -q
.venv\Scripts\python.exe -m relpath.eval --db data\shop.duckdb
```

---

## Faz 2 — Büyüme (SIRADA)

Hedef: PoC'u dağıtılabilir, kurulabilir ve daha geniş görev yelpazesini karşılar hale getirmek.
Local-first tezi korunur — yeni konnektörler hep **opsiyon**, asla zorunluluk.

### 2.1 Postgres / MySQL konnektörleri — **L**
- **Gerekçe:** Gerçek üretim verisi çoğunlukla Postgres/MySQL'de; `connect.py` bugün bunları `NotImplementedError` ile reddediyor.
- **Bağımlılık:** Yeni backend `DuckDBBackend` arayüzünü (tables/columns/row_count/distinct_count/load/query/close) implemente etmeli; `open_backend()` URL routing. Pandas 2.2.x pini ve `_normalize_dtypes()` woodwork uyumu korunmalı.
- **Local-first notu:** Bağlantı kullanıcının kendi sunucusuna; veri makineden çıkmaz.

### 2.2 PyPI yayını + CI — **M**
- **Gerekçe:** `pip install relpath` tek-komut kurulum; "GitHub-first launch" (SPEC §9.1) bunu gerektirir.
- **Bağımlılık:** `pyproject.toml` zaten extras tanımlı (nlp/explain/tabpfn/demo/eval/dev) ve `requires-python = ">=3.10"`. Henüz `.github/workflows/ci.yml` **yok** (HANDOVER backlog'unda). CI matrisi `requires-python >=3.10` aralığını ve dev env Python 3.11'i kapsamalı; `pytest tests\ -q` + `ruff` koşmalı. **Önemli:** `pyproject` bugün gevşek alt sınır kullanır (`pandas>=2.0`); pandas 2.2.x **hard pin'i dokümanla zorlanıyor** (GOLDEN RULE 3 / HANDOVER), `pyproject` ile değil — CI'yi bu kuralı (örn. `pandas>=2.2,<2.3`) gerçekten dayatacak şekilde kurmak bu item'ın işidir. **GOLDEN RULE:** push/release sadece kullanıcı "pushla" dediğinde.
- **Not:** Lisans disiplini — çekirdek MIT/BSD/Apache; getML (ELv2) ve TabPFN-2.5 (ticari yasak) extras'ta karantinada kalır.

### 2.3 Daha çok dikey şablon + testleri — **M**
- **Gerekçe:** Şablonlar time-to-value'yu dakikalara indirir (SPEC Sütun 4) ve dikey SEO sağlar. Bugün 3 var (churn/forecast/fraud).
- **Bağımlılık:** Her yeni şablon `templates.py`'a parametrik PQL builder + `engine.py` template metodu + sample DB üzerinde test. Yeni alan yeni FK yolu gerektirebilir → `schema.py` join_path yeterli olmalı.
- **Aday görevler:** reactivation/win-back, LTV/CLV regresyonu, next-purchase-category, return-risk'in ürün-seviyesine taşınması.

### 2.4 Canlı Claude NL→PQL (web demo) — **M**
- **Gerekçe:** "Veritabanıyla konuşma" deneyimi en yüksek algılanan değer; SPEC §9.1'de developer-lead toplama aracı.
- **Bağımlılık:** `nlp.py` zaten Claude + offline fallback. Gereken: `ANTHROPIC_API_KEY` yönetimi, `RELPATH_LLM_MODEL` (varsayılan `claude-sonnet-4-6`) override, Streamlit demo'da (`demo_app.py`) güvenli key girişi. **GOLDEN RULE 5:** key yoksa offline şablon yolu bozulmamalı.

### 2.5 RDL / GNN backend (relbench + PyG) — **L**
- **Gerekçe:** GNN'in net üstünlüğü link-prediction / öneri ve derin çok-hop görevlerde (SPEC §2.4). Tablo-düzeyi clf/reg için baseline yeter; GNN talep geldikçe.
- **Bağımlılık:** `relbench_adapter.py` iskeleti var ama **build ortamında çalıştırılmadı (untested)** — relbench/torch kurulu değil. Önce eval extra'sını kurup adapter'ı gerçekten koşturmak gerekir. Opsiyonel/plugin olarak kalır; çekirdek torch'suz.

### 2.6 Kalibrasyon / belirsizlik — **M**
- **Gerekçe:** Sınıflandırma olasılıkları (churn/fraud) karar için kalibre olmalı; tahmine güven aralığı eklemek açıklanabilirliği (SPEC §7) güçlendirir.
- **Bağımlılık:** `model.py` `TrainedModel.predict` çıktısı üzerine; sklearn ile calibration (Platt/isotonic), regresyonda quantile/interval. `result.py` metriklerine reliability eklenebilir.

---

## Faz 3 — Vizyon

Uzun-vadeli, talep ve gelir kanıtlandıkça. Hiçbiri local-first sözünü bozmaz: warehouse erişimi
**read-only opsiyon**, foundation-model **in-context** kalır.

### 3.1 Warehouse konnektörleri — Snowflake / Databricks (read) — **L**
- **Gerekçe:** Büyük kurumsal veri warehouse'ta yaşar; "yanında çalış, dışarı taşıma" yorumunu (SPEC §4.3) warehouse'a genişletir.
- **Bağımlılık:** Faz 2.1 backend arayüzü olgunlaşmış olmalı → aynı kontrat üzerine read-only konnektör. Veri hareketi minimumda (push-down sorgu).

### 3.2 Relational Foundation Model (in-context, zero-train) — **L**
- **Gerekçe:** KumoRFM'in asıl arenası; relpath bugün bilinçli olarak görev-başına eğitilen baseline (SPEC §1.3). Foundation-model yolu vizyon, vitrin değil.
- **Bağımlılık:** Faz 2.5 GNN backend + ciddi compute. Lisans/izin disiplini (GOLDEN RULE 4) korunmalı.

### 3.3 Streaming / real-time scoring — **L**
- **Gerekçe:** Batch tahminden online serving'e; düşük gecikmeli karar (fraud gibi) için.
- **Bağımlılık:** Eğitilmiş model artefaktının ayrıştırılması + cutoff mantığının streaming anchor'a uyarlanması. `model.py`/`features.py` serileştirme gerektirir.

### 3.4 Multimodal / metin sütunları — **M/L**
- **Gerekçe:** Bugün text sütunlar `features.py`'da DFS'ten eleniyor; metin muhakemesi Kumo'nun da zayıf noktası (SPEC §2.1).
- **Bağımlılık:** Embedding/LLM ile text → öznitelik füzyonu; provenance açıklamasının (explain.py) text kaynağı taşıyacak şekilde genişletilmesi.

### 3.5 Managed / open-core teklifi — **L**
- **Gerekçe:** OSS → ticari köprü (SPEC §9.1): çekirdek bedava, gelir managed/warehouse/ekip özellikleri.
- **Bağımlılık:** Faz 3.1 warehouse konnektörleri + çok-kullanıcılı operasyon. Çekirdek MIT kalır (GOLDEN RULE 2/4).

---

## Faz 2/3 Backlog Özeti

| # | Item | Faz | Efor | Bağımlılık |
|---|---|---|---|---|
| 2.1 | Postgres/MySQL konnektör | 2 | L | backend arayüzü; pandas 2.2.x |
| 2.2 | PyPI yayını + CI | 2 | M | pyproject extras; CI'de pandas 2.2.x kuralını dayat; "pushla" onayı |
| 2.3 | Daha çok dikey şablon + test | 2 | M | templates.py / engine.py / join_path |
| 2.4 | Canlı Claude NL→PQL demo | 2 | M | nlp.py; ANTHROPIC_API_KEY; offline fallback |
| 2.5 | RDL/GNN backend (relbench+PyG) | 2 | L | relbench_adapter (untested); eval extra |
| 2.6 | Kalibrasyon / belirsizlik | 2 | M | model.py predict; result.py |
| 3.1 | Warehouse read (Snowflake/Databricks) | 3 | L | 2.1 backend olgunluğu |
| 3.2 | Relational Foundation Model | 3 | L | 2.5 GNN; compute; lisans disiplini |
| 3.3 | Streaming / real-time scoring | 3 | L | model/features serileştirme |
| 3.4 | Multimodal / metin sütunları | 3 | M/L | embedding füzyonu; explain genişletme |
| 3.5 | Managed / open-core | 3 | L | 3.1; çok-kullanıcı operasyon |

---

## Değişmez Kurallar (her item için geçerli)

1. **Push yok** — `git push` / PR / merge yalnızca kullanıcı **"pushla"** dediğinde. Lokal commit iş bitiminde.
2. **pandas 2.2.x pinli** — pandas 3.0 woodwork'ü kırar (`.ww` şeması kalıcı olmaz, EntitySet build başarısız). Yükseltme yok.
3. **Çekirdek izinli lisans** (MIT/BSD/Apache). getML (ELv2) ve TabPFN-2.5 (ticari yasak) sadece opsiyonel/karantina.
4. **Local-first ürün tezidir** — veri makineden çıkmak zorunda kalmamalı; DuckDB varsayılan.
5. **Windows:** `PYTHONUTF8=1` (veya `relpath._io.sprint`) ile Türkçe konsol çıktısı cp1252'de çökmemeli.

---

> **Hatırlatma:** Bir item'a *bugün* başlanacaksa, onu buradan değil
> `docs/HANDOVER.md` → **"Sıradaki İş"**'ten yürütün. ROADMAP "nereye"yi, HANDOVER "şimdi neyi"yi anlatır.
