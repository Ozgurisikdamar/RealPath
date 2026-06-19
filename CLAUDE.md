# relpath.dev — SESSION BRAIN (her session bunu OKU)

> Bu dosya **otomatik yüklenir** ve bir session'ın okuduğu **ilk** şeydir. Amaç: kullanıcının hiçbir şeyi
> tekrar anlatmak zorunda kalmaması. Burası operasyon kılavuzu — tek doğruluk kaynağı. Faktları uydurma;
> bir komut/yol/metrik buradaysa kullan, yoksa önce koddan veya `docs/`'tan doğrula.

---

## 1. relpath NEDİR + DURUM

**relpath**, açık kaynaklı, self-hostable, **LOCAL-FIRST** bir relational prediction engine'dir. Bir veritabanı
bağlarsın, tahmin sorusunu düz dilde ya da **PQL** ile sorarsın, veriyi hiçbir yere taşımadan **açıklamalı**
(explained) bir cevap alırsın. Konumlandırma: **Kumo.AI / KumoRFM'in açık kaynak karşılığı.** Akış:
`connect → schema (FK grafiği) → PQL compile (join çıkarımı + zaman penceresi izolasyonu) → features
(DFS + cutoff_time) → model (LightGBM/TabPFN) → explain (join-path provenance)`.

**DURUM (2026-06-19):**

| Alan | Değer |
|---|---|
| Faz | **Phase 1 PoC — tamam** (çalışan uçtan uca hat) |
| Versiyon | `0.1.0` |
| Testler | **12/12 geçiyor** |
| Git | lokal repo, **1 commit** (`5953440`), branch **`master`**, **remote YOK**, **push YOK** |
| Python | **3.11.9**, venv `.venv\` |
| pandas | **2.2.3 (PİNLİ — yükseltme!)** |

---

## 2. "DEVAM ET" PROTOKOLÜ

Kullanıcı **"devam et" / "continue"** dediğinde, hangi model olursan ol şu adımları **sırayla** uygula:

1. **`docs/HANDOVER.md`** dosyasının **"Sıradaki İş"** bölümünü oku — önceliklendirilmiş backlog buradadır.
2. Gerekirse **`docs/ROADMAP.md`** ve **`docs/ARCHITECTURE.md`**'i oku (bağlam/karar için).
3. **En üstteki işaretsiz (unchecked) maddeyi** seç.
4. Env'in çalıştığını **smoke test** ile doğrula (Bölüm 5).
5. **`docs/SKILLS.md`** reçetelerini izleyerek implemente et.
6. **`python -m pytest tests/ -q`** + **`python -m relpath.eval`** çalıştır.
7. **`docs/HANDOVER.md`**'i GÜNCELLE: maddeyi "done" işaretle, yeni sıradaki işleri ekle, tarih/model satırını güncelle.
8. **Sadece lokal commit** at (Bölüm 3, Kural 1 — **push YOK**).

---

## 3. ALTIN KURALLAR (NON-NEGOTIABLE — her session geçerli)

1. **PUSH YOK.** Kullanıcı açıkça **"pushla" / "push"** demedikçe `git push`, PR açma, merge **YASAK**. Lokal commit
   serbest ama **bir iş biriminin SONUNDA** (her küçük adımda değil). Commit'ten sonra **dur** ve onay bekle.
2. **Commit kimliği global gitconfig'ten gelir** (author `Özgür Işık Damar`, GitHub no-reply email). **ASLA**
   `Co-Authored-By: Claude` veya herhangi bir Claude trailer/imza ekleme. Commit mesajları: **kısa, insanca, İNGİLİZCE.**
3. **pandas `2.2.x`'te kalır** (`2.2.3`). pandas 3.0 **woodwork'ü bozar** — `.ww` accessor şeması persist olmaz,
   Featuretools EntitySet build başarısız olur. **Yükseltme.**
4. **Core bağımlılıklar permissive lisanslı kalır** (MIT/BSD/Apache). **getML (ELv2)** ve **TabPFN-2.5
   (non-commercial)** KARANTİNADA — sadece optional/plugin, **asla** core dependency.
5. **NL→PQL** için Claude yolu **`ANTHROPIC_API_KEY`** ister; yoksa **offline template fallback** devreye girer.
   Varsayılan model id **`claude-sonnet-4-6`** (env **`RELPATH_LLM_MODEL`** ile override).
6. **Local-first ürün tezidir:** veri makineden çıkmak zorunda **olmamalı**. **DuckDB varsayılan kalır.**
7. **Windows'ta `PYTHONUTF8=1`** tercih et (ya da `relpath._io.sprint`'e güven) ki Türkçe metin cp1252 konsolu çökertmesin.

---

## 4. HIZLI KURULUM

```powershell
# repo kökü: C:\Users\isiko\OneDrive\Desktop\AI Projects\relpath
.venv\Scripts\python.exe -m pip install -e .       # editable install; entry point: relpath
$env:PYTHONUTF8 = "1"                               # Türkçe konsol çıktısı için
```

- **pandas == 2.2.3** pinli kalır (Altın Kural 3). `pip install -e .` bunu zaten pinler — elle bump etme.
- Bu env'de **kurulu**: core + `anthropic` + `shap` + `streamlit` + `pytest`. **Kurulu DEĞİL**: `torch` / `relbench` / `tabpfn`.
- Optional extras (pyproject): `nlp=anthropic`, `explain=shap`, `tabpfn=tabpfn`, `demo=streamlit`,
  `eval=relbench+torch+torch-frame`, `dev=pytest,ruff`.

---

## 5. DOĞRULAMA (smoke test)

```powershell
$env:PYTHONUTF8 = "1"
.venv\Scripts\python.exe data\make_sample_db.py data\shop.duckdb   # .duckdb gitignored — yeniden üret
.venv\Scripts\python.exe -m pytest tests\ -q                       # 12 passed beklenir
.venv\Scripts\python.exe -m relpath.eval                           # relational vs no-relational baseline
# opsiyonel demo:
streamlit run relpath\demo_app.py                                  # http://localhost:8501
```

**Beklenen sonuçlar** (sample DB üzerinde doğrulanmış):

| Kontrol | Beklenen |
|---|---|
| pytest | **12 passed** |
| churn ROC-AUC | **~0.749** (entity-only baseline ~0.704, **delta +0.045**) |
| customer return-risk (2-hop join, 90 günlük pencere) | **~0.689** ROC-AUC |
| product demand forecast (varsayılan `forecast()`: `SUM(transactions.quantity)`, 3 ay) | **MAE ~8.4** (rmse ~10.1) |

> Not: forecast metriği, engine'in varsayılan `forecast()` helper'ına — yani
> `PREDICT SUM(transactions.quantity, 0, 3, months) FOR EACH products.product_id` — karşılık gelir. Farklı agg/pencere
> seçersen sayı değişir (örn. 1 ay SUM quantity ~4.5; 3 ay COUNT ~3.7); bu satırı bu varsayılan sorgu için referans al.

---

## 6. REPO HARİTASI

```
relpath/
├── __init__.py            # connect, Engine, PredictionResult, parse_pql, PredictiveTask; __version__ 0.1.0
├── connect.py             # DuckDBBackend + open_backend(); DuckDB only (Postgres/MySQL -> NotImplementedError)
├── schema.py              # Column/ForeignKey/Table/RelationalSchema; infer_schema (PK/FK/time index), join_path (BFS), build_entityset
├── pql/
│   ├── ast.py             # TimeWindow, TargetAgg, Comparison, Filter, PredictiveTask; AGGS={COUNT,SUM,AVG,MEAN,MIN,MAX}
│   ├── parser.py          # parse_pql -> PredictiveTask (regex + sqlglot); PQLSyntaxError; MEAN -> AVG alias
│   └── compile.py         # compile_task/CompiledTask; _validate, _join_sql (multi-hop), default_anchors, build_split (universe/events CTE, COALESCE 0)
├── features.py            # synthesize (ft.dfs + cutoff_time = leakage-safe), FeatureMatrix, align_xy
├── model.py               # fit_model -> TrainedModel; LightGBM (clf/reg), degenerate-target guard, optional TabPFN
├── explain.py             # provenance(feature_name), global_importance, explain_entity (SHAP else gain), format_card
├── nlp.py                 # nl_to_pql (Claude via anthropic; re-parse validation); offline template fallback (TR+EN)
├── result.py              # PredictionResult (global_importance/explain/top/head/to_csv); _io.sprint
├── engine.py              # Engine.predict (PQL vs NL auto-detect); churn/forecast/fraud templates; _metrics
├── templates.py           # TEMPLATES + churn_pql/forecast_pql/fraud_pql
├── eval.py                # evaluate_local (relational vs baseline), evaluate_relbench (eval extra), CLI main()
├── relbench_adapter.py    # run_relbench_task (relbench+torch, lazy); eval extra; BUILD ENV'DE ÇALIŞTIRILMADI
├── cli.py                 # argparse: make-sample, schema, ask, predict, eval; entry point relpath
├── demo_app.py            # Streamlit app (port 8501, Türkçe UI)
└── _io.py                 # sprint (encoding-safe print), use_utf8

data/make_sample_db.py     # sentetik e-ticaret DuckDB üretir (seed 42)
tests/                     # conftest (sample_db fixture) + test_pql_parser (10) + test_leakage (2) = 12 pass
docs/                      # aşağıdaki DOCUMENT INDEX
```

**Sample DB şeması** (4 tablo, seed 42, ~18 ay, ~1200 müşteri, ~14343 işlem, ~2209 iade):
- `customers(customer_id PK, signup_date, country, segment)`
- `products(product_id PK, category, brand, price)`
- `transactions(tx_id PK, customer_id FK, product_id FK, tx_time, quantity, amount)`
- `returns(return_id PK, tx_id FK, return_time, reason)`

Churn öğrenilebilir; returns'te gizli per-customer propensity var (gelecekteki return-risk tahmin edilebilir).

**PQL GRAMMAR:**

```
PREDICT AGG(table.col|*, start, end, unit) [op value] FOR EACH entity_table.primary_key
  [WHERE filter] [ASSUMING filter]
```

- `AGG` ∈ `{COUNT, SUM, AVG, MIN, MAX}` (parser ayrıca `MEAN` kabul eder → `AVG`'e alias).
- `unit` ∈ `{days, weeks, months}` · `op` ∈ `{==, !=, >, >=, <, <=}`.
- Comparison **var** ⇒ classification, **yok** ⇒ regression.
- `WHERE` = label'a sayılan target satırlarını filtreler; `ASSUMING` = hangi entity'lerin skorlanacağını kısıtlar.

**DATA-FLOW:** `connect → schema → PQL compile → features → model → explain`.

### DOCUMENT INDEX (hepsi `docs/` altında mevcut — yeniden oluşturma)

| Dosya | İçerik |
|---|---|
| [`docs/INDEX.md`](docs/INDEX.md) | Tüm dokümanların giriş haritası |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Mimari + modül kararları |
| [`docs/HANDOVER.md`](docs/HANDOVER.md) | **"Sıradaki İş" backlog — DEVAM ET buradan başlar** |
| [`docs/SKILLS.md`](docs/SKILLS.md) | Implementasyon reçeteleri |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Fazlar / yol haritası |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Karar günlüğü (ADR) |
| [`docs/RELPATH_SPEC_v2.md`](docs/RELPATH_SPEC_v2.md) | v2 strateji & teknik spec (`.docx`/`.html` + `logo.svg`/`logo.png` yanında) |

---

## 7. YENİ SESSION İSEN — 3 SATIRLIK CHECKLIST

- [ ] **`docs/HANDOVER.md`** "Sıradaki İş"i oku, en üstteki işaretsiz maddeyi al.
- [ ] Bölüm 5 smoke test'i çalıştır (**12 passed** görmelisin), sonra Bölüm 2 protokolünü izle.
- [ ] İş bitince **sadece lokal commit** — kullanıcı **"pushla"** demeden **push YOK** (Bölüm 3).
