# realpath.dev — Mimari (ARCHITECTURE)

> Derin teknik referans. Bu doküman `realpath/` paketindeki gerçek kodu temel alır;
> her açıklama gerçek imza ve davranışla eşleşir. Tek doğru kaynak (single source of truth)
> koddur — burada koddaki bir şeyle çelişen hiçbir komut/yol/fonksiyon yoktur.

**realpath.dev**, açık kaynak, self-hostable ve **local-first** bir ilişkisel tahmin
motorudur (relational prediction engine). Bir veritabanına bağlanır, tahmine dayalı bir
soruyu düz dilde ya da PQL ile sorar ve **açıklanmış** (explained) bir cevap alırsınız —
veriyi hiçbir yere taşımadan. Konum olarak Kumo.AI / KumoRFM'in açık kaynak karşılığıdır.

- **Sürüm:** `__version__` = `0.1.0`
- **Python:** `pyproject.toml` `requires-python = ">=3.10"` (paket desteği). Bu repo'nun
  geliştirme ortamı **3.11** virtualenv `.venv` (`.venv\Scripts\python.exe`) konvansiyonunu kullanır.
- **Lisans çekirdeği:** sadece izin-verici (MIT/BSD/Apache). `pyproject` core bağımlılıkları gevşek
  kısıtlarla bildirir — `duckdb>=0.10`, `pandas>=2.0`, `numpy>=1.24`, `featuretools>=1.30`,
  `lightgbm>=4.0`, `scikit-learn>=1.3`, `sqlglot>=23`. **Not:** `pandas` paket-spec'te `>=2.0`'dır;
  `2.2.3` pin'i kuralla/ortamla zorlanır (woodwork kırılmasın diye — §9), paket metadata'sıyla değil.
- **Opsiyonel ekstralar (`[project.optional-dependencies]`):** `nlp=anthropic` · `explain=shap` ·
  `tabpfn=tabpfn` · `demo=streamlit` · `eval=relbench+torch+torch-frame` · `dev=pytest,ruff`.
  TabPFN yolu **`tabpfn`** ekstrasının arkasındadır (§6/§10).

---

## 1. Sistem Genel Bakış + Veri Akışı

Tek bir tahmin (`Engine.predict`) altı aşamadan geçer. Her aşama ayrı bir modülde yaşar ve
bir sonrakine net bir veri yapısı (dataclass) devreder.

```
   kullanıcı sorusu (NL veya PQL)
            │
            ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  connect.py        open_backend(source) ──▶ DuckDBBackend                      │
 │   (local-first)    veri makineyi terk etmez; tek-dosya in-process DuckDB        │
 └──────────────────────────────────────────────────────────────────────────────┘
            │  backend
            ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  schema.py         infer_schema(backend) ──▶ RelationalSchema                  │
 │                    PK / FK / time-index sezgisi  →  FK grafiği                  │
 └──────────────────────────────────────────────────────────────────────────────┘
            │  schema (FK grafiği)
            ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  nlp.py (opsiyonel)  nl_to_pql(question, schema) ──▶ PQL metni                  │
 │  pql/parser.py       parse_pql(text)            ──▶ PredictiveTask (AST)        │
 │  pql/compile.py      compile_task(...)          ──▶ CompiledTask               │
 │                      • join inference (BFS FK path, multi-hop)                  │
 │                      • temporal decomposition (feature t≤t*  vs  label (t*+a,t*+b]) │
 │                      • build_split(anchor) ──▶ Split (cutoff, labels)           │
 └──────────────────────────────────────────────────────────────────────────────┘
            │  Split.cutoff (entity_key, time)
            ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  features.py       synthesize(es, schema, target_table, cutoff, max_depth=2) ──▶ FeatureMatrix │
 │                    Featuretools DFS + cutoff_time (leakage-safe)                │
 └──────────────────────────────────────────────────────────────────────────────┘
            │  X (entity id'ye göre indeksli), y
            ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  model.py          fit_model(X, y, task_type) ──▶ TrainedModel                 │
 │                    LightGBM (clf/reg) | degenerate guard | opsiyonel TabPFN     │
 └──────────────────────────────────────────────────────────────────────────────┘
            │  predictions + model
            ▼
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │  explain.py        provenance(feature_name) ──▶ (tables, agg)                  │
 │  result.py         PredictionResult: top(), explain(), global_importance()     │
 │                    DFS feature adı = okunabilir join-path → açıklama kartı       │
 └──────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
   açıklanmış cevap (global driverlar + entity-bazlı join-path kartı)
```

Özet veri akışı:

```
connect → schema (FK grafiği) → PQL compile (join inference + temporal window isolation)
        → features (DFS + cutoff_time) → model (LightGBM/TabPFN) → explain (join-path provenance)
```

---

## 2. Modül-Modül Kontratlar (Contracts)

Paket: `realpath/`. Aşağıdaki her satır gerçek imzaya sadıktır.

### `__init__.py`
- **Sorumluluk:** Genel API yüzeyi. Dışa açar: `connect`, `Engine`, `PredictionResult`,
  `parse_pql`, `PredictiveTask`. `__version__ = "0.1.0"`.

### `connect.py` — bağlantı katmanı (local-first)
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `DuckDBBackend(path=":memory:", read_only=True)` | dosya yolu / `:memory:` | backend nesnesi |
| `.tables()` | — | `list[str]` (main şema tabloları) |
| `.columns(table)` | tablo adı | `list[ColumnInfo(name, sql_type)]` |
| `.row_count(table)` | tablo adı | `int` |
| `.distinct_count(table, column)` | tablo, kolon | `(n_non_null, n_distinct_non_null)` |
| `.load(table)` | tablo adı | `pd.DataFrame` (tüm satırlar) |
| `.query(sql, params=None)` | SQL + parametreler | `pd.DataFrame` |
| `.close()` | — | — |
| `open_backend(source)` | yol / `:memory:` / `postgres://` / `mysql://` | `DuckDBBackend` / `PostgresBackend` / `MySQLBackend` |
| `PostgresBackend(dsn, schema="public")` | `postgresql://` DSN | backend nesnesi (`postgres` extra) |
| `MySQLBackend(dsn)` | `mysql://` DSN | backend nesnesi (`mysql` extra) |

- `.distinct_count` ilk eleman `COUNT("column")`'dur — yani **NON-NULL** değer sayısı, satır
  sayısı **değil**. Kolonda hiç NULL yoksa `n_rows`'a eşittir (örn. `customers.country` NULL içermez
  ⇒ `(1200, 5)`). PK sezgisi (§8) bunu satır sayısına eşitlik için kullanır.
- `open_backend`: `.duckdb`/`.db`/`.ddb` veya `:memory:` ⇒ DuckDB; `postgresql://`/`postgres://`
  ⇒ **`PostgresBackend`** (`postgres` extra); `mysql://` ⇒ **`MySQLBackend`** (`mysql` extra). Diğer
  URL şemaları **Phase-2**'dir ve net bir `NotImplementedError` fırlatır. Çıplak yol DuckDB varsayılır.
- `PostgresBackend`: aynı arayüz; `?` placeholder'larını psycopg `%s`'e çevirir, `public` şemasını
  introspect eder, read-only bağlanır. **Docker `postgres:16` ile doğrulandı** (churn 0.7492).
- `MySQLBackend`: aynı arayüz; oturumda **`ANSI_QUOTES`** açar (çift-tırnaklı SQL çalışsın), `?`→`%s`,
  `DATABASE()` ile introspect. **Docker `mysql:8` ile doğrulandı** (churn 0.7492, DuckDB/Postgres ile
  birebir). Yükleyiciler: `data/load_postgres.py`, `data/load_mysql.py`.
- Dosya backend'leri `read_only=True` açılır; `:memory:` için yok sayılır.

### `schema.py` — şema + FK grafiği sezgisi
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `Column(name, sql_type, role)` | — | dataclass; `role ∈ {pk, fk, time, numeric, categorical, text}` |
| `ForeignKey(child_table, child_column, parent_table, parent_column)` | — | dataclass |
| `Table(name, columns, primary_key, time_index)` | — | `.column(name)`, `.feature_columns` |
| `RelationalSchema(tables, foreign_keys)` | — | `.neighbors(t)`, `.join_path(a,b)`, `.describe()` |
| `infer_schema(backend)` | `DuckDBBackend` | `RelationalSchema` |
| `build_entityset(backend, schema, name="db")` | backend, schema | Featuretools `EntitySet` |

- `RelationalSchema.join_path(src, dst)`: yönsüz FK grafiği üzerinde **BFS**; en kısa
  (multi-hop) FK yolunu `list[ForeignKey]` olarak verir, yoksa `None`.
- `_normalize_dtypes(df)`: DuckDB çıktısını woodwork'ün kabul ettiği dtype'lara çevirir
  (`datetime64[ns]`, `object`).

### `pql/ast.py` — soyut sözdizimi
- `TimeWindow(start, end, unit)`: `.bounds(anchor)` yarı-açık `(lo, hi]` döndürür;
  `.horizon_days` = `abs(end) * {days:1, weeks:7, months:30}[unit]`.
- `TargetAgg(func, table, column, window)` — `column=None` ⇒ `COUNT(*)`.
- `Comparison(op, value)`, `Filter(table, column, op, value)`.
- `PredictiveTask(target, entity_table, entity_key, comparison, where, assuming, raw)` —
  `.task_type` = comparison varsa **classification**, yoksa **regression**.
- `shift(anchor, n, unit)`: `days`/`weeks` için `Timedelta`, `months` için `DateOffset`.

### `pql/parser.py` — PQL parser
- `parse_pql(text) -> PredictiveTask`. Üst-seviye yapı regex (`_PREDICT_RE`, `_AGG_RE`),
  `WHERE`/`ASSUMING` filtre ifadeleri **sqlglot** (`read="duckdb"`) ile parse edilir.
- `MEAN` → `AVG` alias'lanır. Hatalarda `PQLSyntaxError`.

### `pql/compile.py` — PQL derleyici
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `compile_task(task, schema, backend)` | AST + schema + backend | `CompiledTask` |
| `CompiledTask._validate()` | — | doğrulama; hata ⇒ `PQLCompileError` |
| `CompiledTask.path` | — | `list[ForeignKey]` (join yolu) |
| `CompiledTask.data_range()` | — | `(min_time, max_time)` |
| `CompiledTask.default_anchors()` | — | `(train_anchor, test_anchor)` (normalize) |
| `CompiledTask.build_split(anchor)` | anchor `Timestamp` | `Split(anchor, entity_key, cutoff, labels, target_value)` |

### `features.py` — leakage-safe öznitelik sentezi
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `synthesize(es, schema, target_table, cutoff, max_depth=2)` | EntitySet + cutoff | `FeatureMatrix(X, definitions, cutoff_time)` |
| `align_xy(fm, labels)` | FeatureMatrix + label serisi | `(X, y)` (entity id'de inner join) |
- `AGG_PRIMITIVES = [count, sum, mean, max, min, std, num_unique]`
- `TRANS_PRIMITIVES = [month, weekday]`

### `model.py` — model katmanı
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `fit_model(X, y, task_type, backend="auto")` | X, y, görev tipi | `TrainedModel` |
| `TrainedModel.predict(X)` | X | sınıf-1 olasılığı (clf) ya da değer (reg) |
| `TrainedModel.importance()` | — | `pd.Series` (LightGBM gain, azalan) |
- `_Preprocessor`: kategorikleri sabit kategorilerle `category`'ye caster; `_clean` ∞→NaN
  yapar ve tamamen null kolonları düşürür.

### `explain.py` — açıklanabilirlik
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `provenance(name)` | DFS feature adı | `(tables: list[str], agg: str\|None)` |
| `prettify(name)` | feature adı | okunabilir string |
| `global_importance(model, top_n=10)` | model | `DataFrame[feature, gain, tables, agg]` |
| `explain_entity(model, X, entity_id, top_n=5)` | model, X, id | `list[Contribution]` (SHAP varsa, yoksa gain) |
| `format_card(entity_id, score, contribs, task_type)` | — | ASCII-güvenli join-path kartı |

### `nlp.py` — doğal dil → PQL
| Üye | Girdi | Çıktı |
|-----|-------|-------|
| `nl_to_pql(question, schema, model=DEFAULT_MODEL, max_retries=2)` | soru + schema | `NLResult(pql, source, note)` |
| `schema_summary(schema)` | schema | LLM prompt'una giden özet metin |
- `DEFAULT_MODEL = env REALPATH_LLM_MODEL` ya da `claude-sonnet-4-6`.
- LLM çıktısı **re-parse** ile doğrulanır; parse etmezse hata geri beslenip tekrar denenir.
- `anthropic` yoksa veya `ANTHROPIC_API_KEY` yoksa **offline** deterministik şablon eşleştirici
  (churn/forecast/fraud, Türkçe+İngilizce anahtar kelime yönlendirmesi).

### `result.py` — sonuç kabı
- `PredictionResult(task, predictions, model, X, metrics, entity_key)`.
  Metotlar: `global_importance()`, `explain(entity_id=None)` (global driverlar veya entity
  kartı), `top()`, `head()`, `to_csv()`. Çıktı `_io.sprint` ile yazılır.

### `engine.py` — yüksek seviye motor
- `Engine(backend, schema, name="db")`: `predict(query, max_depth=2, evaluate=True, verbose=False)`,
  `ask(question)`, `describe()`, dikey şablonlar, `close()`.
- **Dikey şablonlar (imzalar + varsayılanlar):**
  - `churn(entity, event, horizon_days=30)` → `PREDICT COUNT(event.*, 0, horizon_days, days) == 0 FOR EACH entity.<pk>`
  - `forecast(entity, event, column, horizon_months=3)` → `PREDICT SUM(event.column, 0, horizon_months, months) FOR EACH entity.<pk>`
  - `fraud(entity, event, horizon_days=60, where=None)` → `PREDICT COUNT(event.*, 0, horizon_days, days) > 0 FOR EACH entity.<pk>` (`where` ⇒ `ASSUMING`)
- `predict`: `query` PQL mi (`PREDICT` ile başlar) yoksa doğal dil mi otomatik ayırt eder;
  train split'te öznitelik üretip model fit eder, test anchor'da skorlar, ground truth'a karşı
  değerlendirir. `_metrics()` clf için `roc_auc`/`accuracy`, reg için `mae`/`rmse` hesaplar.
- `connect(source, name="db")`: backend açar + şema sezer ⇒ `Engine`.

### `templates.py` / `eval.py` / `relbench_adapter.py` / `cli.py` / `demo_app.py` / `_io.py`
- `templates.py`: `TEMPLATES` kaydı + `churn_pql` / `forecast_pql` / `fraud_pql` PQL üreticileri.
- `eval.py`: `evaluate_local(db, pql=None, max_depth=2)` (tam ilişkisel öznitelikler vs entity-only
  baseline), `evaluate_relbench(dataset, task)` (eval extra ister), `main()` eval CLI'si. Çalıştırma:
  `python -m realpath.eval [--db --pql --dataset --task --max-depth]`.
- `relbench_adapter.py`: `run_relbench_task()` — relbench+torch (eval extra) ile özniteliklerimizi
  RelBench görevlerine bağlar (etiketi `cutoff_time`'a koyarak X/y hizalar, id'leri `ignore_columns`'a
  alır). **`rel-f1` ile doğrulandı**: driver-dnf AUC ~0.592, driver-position MAE ~3.61 (test etiketleri
  maskeliyse `val`'a düşer). Not: bu basit DFS baseline, tuned RDL/GNN'in altında — beklenen.
- `cli.py`: argparse alt komutları `make-sample`, `schema`, `ask`, `predict`, `eval`.
  Entry point: `realpath` (veya `python -m realpath.cli`).
- `demo_app.py`: Streamlit (`streamlit run realpath/demo_app.py`, port 8501). Arayüz varsayılan
  İngilizce; Türkçe kenar çubuğundaki dil seçicisiyle ya da `?lang=tr` ile (seçim URL'e yazılır).
  Tüm metinler `TEXT[lang]` sözlüğünde; tema `.streamlit/config.toml`. Kenar çubuğunda keşfedilen
  şema/FK grafiği (`st.graphviz_chart`), sonuçta metrik kutuları + global sürücü grafiği (Altair).
  Davranış CLI ile aynı: `Engine.predict(evaluate=True)` + `explain_entity`/`format_card`.
  Duman testi `tests/test_demo_app.py` (AppTest; `demo` extra, `streamlit>=1.57`).
- `_io.py`: `sprint()` encoding-güvenli print; `use_utf8()` stdout/stderr'i UTF-8'e geçirir.

---

## 3. PQL Derleyici İçi (derinlemesine)

### 3.1 Parse: regex + sqlglot

PQL grameri:

```
PREDICT AGG(table.col|*, start, end, unit) [op value]
FOR EACH entity_table.primary_key
[WHERE filter]
[ASSUMING filter]
```

- **AGG** ∈ `{COUNT, SUM, AVG, MIN, MAX}` (`MEAN` → `AVG`). `unit` ∈ `{days, weeks, months}`.
  `op` ∈ `{==, !=, >, >=, <, <=}`. Comparison varsa **classification**, yoksa **regression**.
- Üst-seviye iskelet `_PREDICT_RE` + `_AGG_RE` regex'leriyle elle parse edilir.
- `WHERE` / `ASSUMING` ifadeleri **gerçek SQL predicate** olarak `sqlglot.parse_one(text, read="duckdb")`
  ile parse edilir; `EQ/NEQ/GT/GTE/LT/LTE` düğümleri `Filter`'lara çevrilir
  (`amount > 1000 AND category = 'shoes'` gibi). Kullanılabilir karşılaştırma yoksa `PQLSyntaxError`.
- **WHERE** = label'a katkı sayan target satırlarını süzer. **ASSUMING** = hangi entity'lerin
  skorlanacağını kısıtlar.

### 3.2 Join inference: BFS FK path (multi-hop)

`CompiledTask.__init__` çağrısı `schema.join_path(entity_table, target.table)` ile entity
tablosundan target tablosuna giden FK yolunu bulur — kullanıcı hiç `JOIN` yazmaz.

- Yol bulunamazsa: `PQLCompileError("No foreign-key path connects ...")`.
- `_join_sql()` bu yolu çok-adımlı `JOIN ... ON ...` zincirine açar; her FK'da yönü
  (child→parent ya da parent→child) doğru tarafa kurar. Örn. customer-level return-risk için
  `customers → transactions → returns` (2-hop) zinciri üretilir.

### 3.3 Temporal decomposition (sızıntı yalıtımı)

Bir **anchor** `t*` için iki pencere kesin ayrılır:

| Pencere | Aralık | Kim üretir |
|---------|--------|------------|
| **Feature window** | `t ≤ t*` | Featuretools DFS, `cutoff_time = t*` ile |
| **Label window** | `(t*+start, t*+end]` (yarı-açık) | `build_split` SQL'i |

Pencereler **asla** çakışmaz ⇒ gelecekten bilgi eğitime sızamaz. `TimeWindow.bounds(anchor)`
yarı-açık `(lo, hi]` sınırlarını verir.

### 3.4 default_anchors()

`data_range()` target time-index'in `MIN/MAX`'ını okur. `horizon = horizon_days` günlük.

```
test_anchor  = max - horizon
train_anchor = test_anchor - horizon
# veri kısa ise (train_anchor <= min): üçte-bir fallback
span = (max - min) / 3
train_anchor, test_anchor = min + span, min + 2*span
```

İkisi de `.normalize()` ile gün başına çekilir.

### 3.5 Split build: universe CTE ⟕ events CTE

`build_split(anchor)` tek bir parametreli SQL kurar. Kavramsal şekli:

```sql
WITH universe AS (              -- anchor'da var olan entity'ler (+ ASSUMING)
    SELECT "<entity>"."<key>" AS _eid
    FROM "<entity>"
    WHERE "<entity>"."<time_index>" <= ?        -- entity time-index varsa
      AND <ASSUMING filtreleri>
),
events AS (                     -- gelecekteki penceredeki target satırları (+ WHERE)
    SELECT "<entity>"."<key>" AS _eid, AGG(<col|*>) AS _val
    FROM "<entity>"
    <multi-hop JOIN zinciri>                    -- _join_sql()
    WHERE "<target>"."<time_index>" >  ?         -- t* + start
      AND "<target>"."<time_index>" <= ?         -- t* + end
      AND <WHERE filtreleri>
    GROUP BY "<entity>"."<key>"
)
SELECT u._eid AS entity_id, COALESCE(e._val, 0) AS agg_value
FROM universe u
LEFT JOIN events e ON u._eid = e._eid
ORDER BY u._eid;
```

- **LEFT JOIN + COALESCE(..., 0):** pencerede hiç olayı olmayan entity'ler `0` değeri alır
  (örn. churn'de "30 günde 0 işlem" tam da pozitif sınıftır).
- `target_value` = ham agregasyon (karşılaştırma öncesi). Comparison varsa
  `_apply_comparison` ile `int` etiketlere (clf), yoksa `float`'a (reg) dönüşür.
- `cutoff` = `[entity_key, time=anchor]` DataFrame'i — doğrudan DFS'e gider.

### 3.6 Doğrulama (`_validate`)

- Entity ve target tabloları şemada olmalı; `FOR EACH` kolonu entity tablosunda **mevcut** olmalı.
- **FOR EACH key, entity tablosunun primary key'i olmalı — _ancak_ bir PK sezildiyse.** Kural
  koşulludur: `if ent.primary_key and t.entity_key != ent.primary_key` ⇒ `PQLCompileError`. Entity
  tablosu için **hiç PK sezilmediyse** (`ent.primary_key is None`), mevcut herhangi bir kolon geçer.
- **Target tablosunun bir time-index'i olmalı** (yoksa gelecek penceresi tanımlanamaz).

---

## 4. Leakage-Safety (sızıntı güvenliği)

### Mekanizma
Featuretools DFS'e entity başına bir `cutoff_time` verilir. DFS yalnızca `time <= cutoff`
satırlarını agregelediğinden hiçbir gelecek bilgisi bir özniteliğe giremez. Bu, §3.3'teki
zamansal ayrımın yapısal garantisidir: feature penceresi (`t ≤ t*`) ve label penceresi
(`(t*+start, t*+end]`) çakışmaz.

### Test bunu nasıl kanıtlıyor (`tests/test_leakage.py`)
- **Truncation testi:** anchor sonrası **tüm** satırlar silinir; öznitelik matrisinin
  **aynı kaldığı** assert edilir. Eğer DFS gelecek satırları görseydi matris değişirdi —
  değişmemesi sızıntı olmadığını kanıtlar.
- Ayrıca label penceresinin **kesinlikle gelecekte** (anchor'dan sonra) olduğu kontrol edilir.
- **12 test geçer** (`python -m pytest tests/ -q`).

```bash
.venv\Scripts\python.exe -m pytest tests/ -q
```

---

## 5. Öznitelik Sentezi (Feature Synthesis)

`features.synthesize(es, schema, target_table, cutoff, max_depth=2)`:

- **DFS:** `ft.dfs(entityset=es, target_dataframe_name=target_table, cutoff_time=cutoff, ...)`.
- **Primitive setleri** (kasıtlı küçük — yeterli sinyal, sınırlı öznitelik patlaması):
  - `AGG_PRIMITIVES = [count, sum, mean, max, min, std, num_unique]`
  - `TRANS_PRIMITIVES = [month, weekday]`
- **`ignore_columns` (`_ignore_columns`):** her tabloda `role ∈ {pk, fk, text}` kolonları
  öznitelik aramasından düşürülür ⇒ id sızıntısı ve gürültülü serbest-metin önlenir.
- **MultiIndex collapse:** DFS bir `(instance, time)` MultiIndex döndürebilir; kod bunu
  entity id'ye indirger (`get_level_values(0)`), sonra `sort_index()`.
- Sonuç `FeatureMatrix(X, definitions, cutoff_time)`. `definitions` = feature adı → okunabilir
  tanım (bu adlar açıklanabilirliği besler, §7).
- `align_xy(fm, labels)`: X ve y'yi entity id üzerinde **inner join** ile hizalar.

---

## 6. Model Katmanı

`model.fit_model(X, y, task_type, backend="auto") -> TrainedModel`:

- **Görev tipi PQL'den gelir:** comparison varsa **classification**, yoksa **regression**
  (`PredictiveTask.task_type`). Ek bir karar gerekmez.
- **`_Preprocessor`:** `object`/`category` kolonları **sabit kategorilerle** pandas
  `category`'ye caster (`fit` kategorileri kaydeder, `transform` aynı kategorilerle uygular ve
  `reindex(columns=...)` ile kolon hizalar). Bu, train/test arasında kategori tutarlılığını
  garanti eder. `_clean` ∞ değerlerini NaN yapar ve tamamen-null kolonları düşürür.
- **Degenerate-target guard:** classification'da `y.nunique() < 2` ise model eğitilmez; sabit
  bir tahminci (`constant`) döner — `predict` tüm satırlara aynı değeri verir.
- **LightGBM:** `LGBMClassifier` / `LGBMRegressor`, sabit parametrelerle
  (`n_estimators=300, learning_rate=0.05, num_leaves=31, subsample=0.8, colsample_bytree=0.8,
  min_child_samples=20, n_jobs=-1, verbosity=-1`).
- **Opsiyonel TabPFN:** sadece `backend="tabpfn"` ya da `auto` + uygun koşullarda
  (`classification`, `len(X) <= 1000`, `<= 100` kolon, paket kurulu). TabPFN sadece sayısal
  kolonları kullanır (`fillna(0.0)`). Kurulu değilse sessizce LightGBM'e düşer. Paket **`tabpfn`
  ekstrasının** arkasındadır (`pip install -e ".[tabpfn]"`) ve bu ortamda **kurulu değildir**.
- `TrainedModel.predict`: clf'de sınıf-1 olasılığı, reg'de ham değer.
  `importance()`: LightGBM **gain** (yalnızca `booster_` varsa).

> TabPFN-2.5 ticari-olmayan lisanslıdır; bu yüzden **karantinada** — yalnızca opsiyonel,
> asla çekirdek bağımlılık değil.

---

## 7. Açıklanabilirlik (Explainability)

Temel fikir: **DFS feature adları zaten ilişkisel provenance'ı kodlar.** Örneğin
`SUM(transactions.amount)` adı → tablo `transactions`, agregasyon `SUM`. Bu, embedding tabanlı
modellere karşı yapısal üstünlüktür: gömme attribution'ları okunabilir join-path değildir.

- `provenance(name)` → `(tables, agg)`. İki regex: `_AGG_RE = ^([A-Z_]+)\(` üst-seviye
  agregasyonu, `_TABLE_RE = ([A-Za-z_]\w*)\.` referans verilen tabloları yakalar (sırayı
  korur, tekrarları atar).
- **Global:** `global_importance(model, top_n)` → LightGBM gain'i tablo/agg ile zenginleştirip
  `DataFrame[feature, gain, tables, agg]` verir.
- **Lokal (entity başına):** `explain_entity(model, X, entity_id)` — **SHAP varsa**
  (`shap.TreeExplainer`) per-row attribution; **yoksa** global gain ağırlıklarına düşer.
- `format_card(...)`: entity başına **ASCII-güvenli** join-path kartı render eder
  (`entity <id> -- probability 0.xxx`, ardından `|-` / `\`-` dallarıyla katkılar). `result.explain(entity_id)`
  bunu kullanır.

---

## 8. Şema Sezgisi Heuristikleri (`infer_schema`)

Çoğu gerçek veritabanı/CSV-DuckDB'sinde **bildirilmiş PK/FK yoktur**. realpath bunları
sezgisel kurtarır:

| Eleman | Kural |
|--------|-------|
| **Primary key** | Bir `*_id` / `id` kolonu; değerleri tablo içinde **benzersiz** (`n == n_rows == d`). İsim, tablonun tekil hâliyle eşleşeni tercih eder: `preferred = {<singular>_id, <tablo>_id, id}`. Eşleşme yoksa ilk benzersiz id. |
| **Foreign key** | PK olmayan bir `*_id` kolonu; adı **başka** bir tablonun primary key'ine eşitse, o tabloya FK olur. |
| **Time index** | İlk `TIMESTAMP`/`DATE`/`TIME` kolonu (satırın "görünür olduğu" an). |
| **Kategorik vs metin** | Sayısal/temporal olmayanlar: `distinct/rows <= 0.5` ⇒ `categorical`, aksi ⇒ `text`. |

- Çözülemeyen id-benzeri kolonlar `text`'e düşürülür (özniteliklere girmez).
- `_singular`: `...ies → ...y`; `...ses → sondaki "es"'i at` (`name[:-2]`, ör. `glasses → glass`,
  `addresses → address`); `...s → ...`.
- Kurtarılan `RelationalSchema` hem **join-path inference** için FK grafiği hem de
  `EntitySet` için plandır.

**Örnek (sample e-ticaret DB):**

| Tablo | PK | FK | time-index |
|-------|----|----|-----------|
| `customers` | `customer_id` | — | `signup_date` |
| `products` | `product_id` | — | — |
| `transactions` | `tx_id` | `customer_id`, `product_id` | `tx_time` |
| `returns` | `return_id` | `tx_id` | `return_time` |

Örnek DB'yi üret:

```bash
.venv\Scripts\python.exe data\make_sample_db.py data\shop.duckdb
```

> `.duckdb` dosyası gitignore'dadır — yeniden üretilir.

---

## 9. Önemli Ortam Notları

- **pandas 2.2.x pin (`pandas==2.2.3`) — DOKUNMAYIN.** pandas 3.0 **woodwork'ü kırar**:
  `.ww` accessor şeması kalıcı olmaz ⇒ Featuretools `EntitySet` build başarısız. Bu, çekirdek
  bir non-negotiable kuraldır.
- **dtype normalizasyonu:** `_normalize_dtypes` DuckDB çıktısını `datetime64[ns]` ve `object`'e
  çevirir ki woodwork kabul etsin. `build_entityset` time-index'i ayrıca `pd.to_datetime` ile
  zorlar; kategorik kolonlara `logical_types={... : "Categorical"}` verir.
- **MultiIndex:** DFS `(instance, time)` MultiIndex döndürebilir; `synthesize` bunu entity id'ye
  indirir (`get_level_values(0)`). Engine, test özniteliklerini `Xte.reindex(columns=Xtr.columns)`
  ile train kolonlarına hizalar.
- **Windows / Türkçe konsol:** `PYTHONUTF8=1` ayarlayın; ayrıca `realpath._io.sprint` encoding-güvenli
  yazar ve CLI/eval `_io.use_utf8()` çağırır (cp1252 konsolu Türkçe metinde çökmesin diye).
- **NL → PQL anahtarı:** Claude yolu için `ANTHROPIC_API_KEY` gerekir; yoksa **offline şablon**
  fallback kullanılır. Varsayılan model id `claude-sonnet-4-6` (env `REALPATH_LLM_MODEL` ile override).
- **Local-first tezi:** veri makineyi terk etmek zorunda kalmamalı; DuckDB varsayılan kalır.

Editable kurulum:

```bash
.venv\Scripts\python.exe -m pip install -e .
```

---

## 10. Genişletme Noktaları (Extension Points)

### Yeni bir DB connector eklemek
- `connect.py`'de `DuckDBBackend`'in küçük yüzeyini (`tables/columns/row_count/distinct_count/load/query/close`)
  uygulayan bir backend yazın ve `open_backend` içinde URL şemasına göre yönlendirin.
- **Postgres ve MySQL ZATEN VAR** (`PostgresBackend`/`MySQLBackend`) — örnek alın. Diğer şemalar
  (örn. BigQuery, Snowflake) hâlâ `NotImplementedError` veren **Phase-2** yer tutuculardır.
- Şemanın geri kalanı (FK sezgisi, DFS, model, explain) backend-agnostiktir; aynı arayüze oturur.

### Yeni bir PQL agregasyonu eklemek
1. `pql/ast.py` içinde `AGGS` kümesine ekleyin (gerekiyorsa `MEAN→AVG` gibi alias).
2. Parser zaten `_AGG_RE` ile `func`'ı yakalar; `AGGS`'a eklemek doğrulamayı açar.
3. `compile.build_split` agregasyonu doğrudan `func(arg)` olarak SQL'e gömer — DuckDB destekli
   bir agregasyonsa ek iş gerekmez. Ham SQL adı farklıysa `agg_expr` üretimini uyarlayın.

### Yeni bir Featuretools primitive eklemek
- `features.py`'de `AGG_PRIMITIVES` veya `TRANS_PRIMITIVES` listesine ekleyin. Setleri küçük
  tutmak öznitelik patlamasını sınırlar; eklediğiniz primitive'in ürettiği feature adının
  `provenance()` regex'leriyle (`AGG(...table.col...)`) okunabilir kalmasına dikkat edin, aksi
  hâlde açıklanabilirlik kartı tabloyu/agg'ı çözemez.

### Phase-2 GNN backend (yüksek seviye)
- Model katmanı `fit_model(X, y, task_type, backend=...)` üzerinden çoğullanır (zaten `auto` /
  `tabpfn` ayrımı var). Bir GNN/RDL backend'i aynı `TrainedModel` kontratını
  (`predict`, `importance`) sağlayan yeni bir `backend` dalı olarak eklenebilir.
- İlişkisel yapı (FK grafiği) ve zamansal yalıtım (`cutoff_time`) zaten mevcut; GNN'e EntitySet
  + cutoff beslenir. **Lisans kuralı:** çekirdek izin-verici kalır; getML (ELv2) ve TabPFN-2.5
  (ticari-olmayan) yalnızca opsiyonel/plugin olarak, asla çekirdek bağımlılık değil.

---

## Doğrulanmış Metrikler (sample DB)

Aşağıdaki tablo **ilişkisel lift** kazanımlarını gösterir: realpath'in cross-table öznitelikleri
entity-only baseline'ı yener.

| Görev | Metrik | realpath | Baseline | Δ (lift) |
|-------|--------|---------|----------|----------|
| Churn (`COUNT(transactions.*, 0, 30, days) == 0`) | ROC-AUC | **~0.749** | ~0.704 | **+0.045** |
| Customer-level return-risk (2-hop join, 30 günlük pencere) | ROC-AUC | **~0.689** | — | ilişkisel kazanım (60d ~0.699, 90d ~0.690) |
| Test paketi | — | **25/25 geçer** | — | — |

> **Forecast hakkında dürüst not (ilişkisel lift tablosuna dahil EDİLMEDİ):** Product demand
> forecast bir *regresyon* görevidir; sayısı seçilen ufka (horizon) güçlü bağlıdır ve bu sentetik
> veride forecast **ilişkisel bir kazanım göstermez** (sinyal per-customer engagement'ta, per-product
> değil). Doğrulanmış sayılar:
> - **3 aylık ufuk** — `forecast()` helper'ının varsayılanı (`templates.forecast_pql`,
>   `horizon_months=3`): `PREDICT SUM(transactions.quantity, 0, 3, months) FOR EACH products.product_id`
>   ⇒ realpath (full) **MAE ~8.41** (rmse ~10.1), entity-only baseline **~7.48** (Δ **+0.93** = *iyileşme yok*).
> - **2 aylık ufuk** (varyant) ⇒ realpath **MAE ~6.75**.
>
> Yani forecast/return-risk, churn'e göre daha **zayıf** showcase'lerdir; **churn asıl göstergedir**
> (ilişkisel lift +0.045). Doğrulama: `.venv\Scripts\python.exe -m realpath.eval --pql "<yukarıdaki PQL>"`.
> Ufuk belirtilmeden tek bir "forecast MAE" değeri yanıltıcıdır; her zaman agg + pencere ile raporlayın.
