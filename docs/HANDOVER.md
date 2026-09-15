# HANDOVER — realpath.dev

> **Son guncelleme: 2026-09-15** · onceki is: **Sprint 2 (3/4)** — DFS tuning (driver-dnf 0.592→**0.658**), ek RelBench task (driver-top3 0.769), GNN CI workflow (`ci/gnn-eval.yml`). Kalan: GNN adil temporal SAYISI **infra-bloke** (disk %100 doldu, Docker bozuldu). ⚠️ **2026-09-15 duzeltmesi:** "GitHub Linux CI'da kosacak" cozumu **YOK** — bu hesapta Actions hic kosmuyor (**ADR-015**); benchmark gercek bir Linux makinesinde elle kosar ya da PENDING kalir.
> Bu bir *living* state dosyasidir. **Her session** commit'ten ONCE bu satiri ve asagidaki checklist'leri guncelle.
> `devam` dendiginde once **`docs/SPRINTS.md`** (🟢 guncel sprint) okunur; **bu dosya canli durumdur** (ne bitti, bilinen sorunlar, dogrulama).

**realpath.dev** — acik kaynak, self-host, **local-first** relational prediction engine. Bir veritabani baglarsin, tahmin sorusunu duz dil veya PQL ile sorarsin, **aciklamali** bir cevap alirsin — veri makineden cikmadan. Kategori lideri **Kumo.AI / KumoRFM**'in acik-kaynak karsiti.

---

## 1) SU ANKI DURUM

**Phase 1 PoC tamamlandi.** Calisan ve dogrulanmis bir uctan-uca hat var:

- **connect → schema (FK grafigi) → PQL compile (join inference + temporal window izolasyonu) → features (DFS + cutoff_time) → model (LightGBM/TabPFN) → explain (join-path provenance)**
- **Dikey sablonlar:** `churn`, `forecast`, `fraud` (fraud, sentetik veride zayif sinyal — asagi bak).
- **NL → PQL:** Claude (anthropic SDK) yolu + API key yoksa **offline deterministik sablon fallback** (churn/forecast/fraud keyword routing, TR+EN). Cikti her zaman tekrar-parse edilerek dogrulanir.
- **Aciklanabilirlik:** global importance + per-entity join-path karti (SHAP varsa, yoksa LightGBM gain fallback).
- **Eval:** `evaluate_local()` realpath full relational feature'lari ile entity-only baseline'i karsilastirir.
- **Testler:** 25/25 gecer. `test_leakage.py` gelecek-sizintisi olmadigini, anchor sonrasi tum satirlari silip feature matrix'in ayni kaldigini gostererek **kanitlar**; ayrica label penceresinin kesin olarak gelecekte oldugunu dogrular.

### Dogrulanmis metrikler (sample DB uzerinde)

| Gorev | Metrik | Deger | Not |
|---|---|---|---|
| Churn (classification) | ROC-AUC | **~0.749** | entity-only baseline ~0.704, delta **+0.045** |
| Customer return-risk (2-hop join) | ROC-AUC | **~0.689** | musteri seviyesine reframe edildi |
| Product demand forecast (varsayılan 3 ay `SUM(quantity)`) | MAE | **~8.41** (rmse ~10.1) | ilişkisel lift YOK (baseline ~7.48); 2 ay varyant ~6.75. **Churn asıl gösterge.** |
| Test suite | pytest | **25/25 pass** (+2 skip: Postgres, MySQL) | |

### Git durumu

- Git repo, branch `master`, **remote `origin` → github.com/Ozgurisikdamar/realpath (private)**, push edildi.
- **KURAL:** kullanici `pushla` (ya da `push`) DEMEDIKCE push / PR / merge YOK. Lokal commit serbest, is bitiminde. (Bu turda kullanici "pushla" dedigi icin pushlandi.)
- **2026-09-15:** ADR-015 + `ci/README.md` uyarisi commit `b87b51f`; kullanici "ana dala pushla" dedigi icin `master`'a ileri sarildi (force push yok, gecmis yeniden yazilmadi).

---

## 2) TAMAMLANANLAR

- [x] DuckDB backend (`connect.py`: tables/columns/row_count/distinct_count/load/query/close, `open_backend`).
- [x] Otomatik sema cikarimi (`schema.py`): PK / FK / time-index heuristikleri + `join_path` BFS (multi-hop FK grafigi).
- [x] Featuretools `EntitySet` build + `_normalize_dtypes` (DuckDB → woodwork-uyumlu dtype coercion).
- [x] PQL grammar + parser (`pql/parser.py`, regex + sqlglot WHERE/ASSUMING), AST (`pql/ast.py`), MEAN→AVG alias.
- [x] PQL compile (`pql/compile.py`): `_validate`, multi-hop `_join_sql`, `default_anchors`, `build_split` (universe ⋈ events, COALESCE 0, gelecek pencere izolasyonu).
- [x] Sizinti-guvenli feature synthesis (`features.py`): `ft.dfs` + `cutoff_time`, AGG/TRANS primitives, pk/fk/text drop, `align_xy`.
- [x] Model katmani (`model.py`): LightGBM clf/reg, categorical preprocessor, degenerate-target guard, opsiyonel TabPFN (sadece kuruluysa, kucuk classification).
- [x] Aciklanabilirlik (`explain.py`): feature-name provenance, global importance, per-entity ASCII join-path karti, SHAP/gain.
- [x] NL→PQL (`nlp.py`): Claude + offline fallback, re-parse validasyon, `schema_summary`.
- [x] `PredictionResult` (`result.py`) + `Engine` (`engine.py`) + sablon registry (`templates.py`).
- [x] Eval harness (`eval.py`): `evaluate_local`, `evaluate_relbench` (extra arkasinda), `main` CLI.
- [x] CLI (`cli.py`): `make-sample / schema / ask / predict / eval`, entry point `realpath`.
- [x] Streamlit demo (`demo_app.py`, port 8501, Turkce UI).
- [x] Sentetik e-ticaret DB generator (`data/make_sample_db.py`, 4 tablo, seed 42).
- [x] Encoding-safe I/O (`_io.py`: `sprint`, `use_utf8`).
- [x] Testler: `test_pql_parser.py` (10), `test_leakage.py` (2), `test_templates.py` (8), `test_calibration.py` (3), `test_cli.py` (2), `conftest.py` (sample_db + engine fixtures) — **25/25** (+2 skip: `test_postgres.py`, `test_mysql.py`).
- [x] Bilingual README (TR/EN) + `docs/REALPATH_SPEC_v2.md` (+ .docx/.html) + logo.
- [x] CI + paketleme: `.github/workflows/ci.yml` (push/PR'da ruff + pytest, py3.10/3.11), `pyproject` metadata (`[project.urls]`, classifiers, **pandas pin `>=2.0,<2.3`**), `[tool.ruff]` + lint temiz. Temiz-oda kurulumla (`pip install -e ".[dev]"`) dogrulandi: pandas 2.2.3.
- [x] GitHub'a push: **private** repo `Ozgurisikdamar/realpath` (origin/master). NOT: `ci.yml` commit'i token'da `workflow` scope olmadigi icin **pushlanmadi** (lokalde bekliyor; `gh auth refresh -h github.com -s workflow` sonrasi pushlanir).
- [x] Per-entity probability **calibration** (opt-in isotonic): `model.py` (`fit_model(calibrate=)`, `reliability()` Brier+ECE), `engine.predict(calibrate=)`, `result.reliability()`. Doğrulandı: ECE 0.033→0.014, AUC korunur; **default kapalı** (headline 0.749 değişmedi).
- [x] **Postgres connector**: `connect.py` `PostgresBackend` + `open_backend` `postgres://` yolu + `postgres` extra (`psycopg`). `?`→`%s` çevirisi, `public` şema introspection. **Docker `postgres:16` ile UÇTAN-UCA DOĞRULANDI**: şema/FK çıkarımı + churn ROC-AUC **0.7492** (DuckDB ile birebir aynı). `data/load_postgres.py` yükleyici, `tests/test_postgres.py` (`REALPATH_TEST_PG` yoksa skip).
- [x] **CONTRIBUTING.md** (repo kökü): kurulum, test/lint, opt-in Postgres testi, guardrail'ler (sızıntı-güvenliği, local-first, lisans), recipe pointer'ları. Setup komutları doğrulanmış (`pip install -e ".[dev]"` → 25 passed, 1 skipped).
- [x] **RelBench adapter DOĞRULANDI**: `relbench_adapter.py` sertleştirildi (dtype normalize, `ignore_columns`, etiketi `cutoff_time`'a koyup X/y hizalama, test maskeli→`val` fallback). İzole `.venv_eval` (torch+relbench) ile `rel-f1` koşturuldu: **driver-dnf AUC ~0.592, driver-position MAE ~3.61** (basit DFS baseline; tuned RDL'in altında, beklenen).
- [x] **CLI `--calibrate` bayrağı**: `realpath predict ... --calibrate` → kalibre olasılık + `result.reliability()` (Brier/ECE) yazdırır. `tests/test_cli.py` (2: schema + predict --calibrate). Canlı doğrulandı: brier ~0.20, ece ~0.085.
- [x] **MySQL connector** (3. backend): `connect.py` `MySQLBackend` (pymysql, `mysql` extra) + `open_backend` `mysql://`. ANSI_QUOTES (çift-tırnak SQL çalışsın) + `DATABASE()` introspection + `?`→`%s`; `_NUMERIC`'e `INT`, `_TEMPORAL`'e `DATETIME` eklendi. **Docker `mysql:8` ile UÇTAN-UCA DOĞRULANDI**: şema/FK + churn **0.7492** (DuckDB/Postgres ile birebir). `data/load_mysql.py`, `tests/test_mysql.py` (skip). → **DuckDB + Postgres + MySQL** üçü de aynı sonucu veriyor (backend-agnostik).
- [x] **RDL/GNN backend implementasyonu** (`realpath/gnn.py`): HeteroEncoder + HeteroTemporalEncoder + HeteroGraphSAGE + NeighborLoader + eğitim döngüsü; `realpath.eval --gnn`. **Kod uçtan-uca DOĞRULANDI** (rel-f1/driver-dnf: eğitilir loss 0.38→0.29, tahmin eder). **AMA** Windows'ta non-temporal fallback → AUC 0.76 **LEAKY, adil değil** (temporal disjoint sampling pyg-lib ister, Windows'ta yok). Adil temporal eval → SIRADAKI (Linux). Ayrıca pyproject `eval` extra düzeltildi: `torch-frame`(impostor)→**`pytorch-frame`** + `torch-geometric`. Opsiyonel/plugin; çekirdek torch'suz (25/2 değişmedi).

---

## 3) SIRADAKI IS → **`docs/SPRINTS.md`**

> **Backlog artık SPRINTS'te.** `devam` → [`docs/SPRINTS.md`](SPRINTS.md) **🟢 GÜNCEL sprint**
> (şu an **Sprint 1 — OSS Launch Readiness**) → en üst açık & bloke-olmayan görev.
>
> **Bloke maddeler** (atla; SPRINTS'te ilgili sprintte): canlı Claude NL→PQL (`ANTHROPIC_API_KEY`
> yok → Sprint 4) · GNN adil temporal benchmark (`pyg-lib` Windows'ta yok → Sprint 2; ⚠️ **kacis yolu sanilan GitHub CI de yok** — ADR-015).

---

## 4) BILINEN SORUNLAR / DIKKAT

- **pandas 3.0 KIRIYOR.** `pandas==2.2.x` (pinli **2.2.3**) sart. pandas 3.0'da `.ww` woodwork accessor semasi kalici olmuyor → Featuretools EntitySet build cokuyor. **Yukseltme.**
- **GNN temporal sampling `pyg-lib` ister (Windows'ta YOK).** `realpath/gnn.py` non-temporal fallback ile koşar ama **LEAKY** (adil benchmark değil). Leakage-safe temporal GNN için Linux/WSL + `pip install pyg-lib`. Ayrıca `eval` extra'da gerçek paket **`pytorch-frame`** (PyPI `torch-frame` impostor; düzeltildi) + `torch-sparse` PyG wheel index'ten.
- **⚠️ DİSK %100 DOLDU + Docker BOZULDU.** GNN'i Linux Docker'da koşma denemesi (torch+PyG ≈2 GB) **C: diskini doldurdu** (0 boş) ve Docker WSL2 storage'ı bozdu (`input/output error`). `.venv_eval` + pip cache silinerek ~2.8 GB açıldı. **Docker artık çalışmıyor** — kullanıcının **Docker Desktop → Troubleshoot → Clean/Purge data** (ya da `wsl --shutdown`) ile sıfırlaması gerekir. Postgres/MySQL testleri Docker'a bağlı (şimdilik skip). ~~GNN adil temporal → GitHub Linux CI (`ci/gnn-eval.yml`)~~ → **BU ÇÖZÜM YOK (2026-09-15, ADR-015):** bu hesapta Actions hiç koşmuyor, `workflow_dispatch` dahil. Adil temporal sayı ya gerçek bir Linux makinesinde elle koşturulur ya da PENDING kalır — ve PENDING olduğu açıkça yazılır.
- **⛔ CI DİYE BİR KAPI YOK — ölçüldü (2026-09-15, ADR-015).** `ci/` klasöründeki iki workflow (`.github/workflows/` değil — token'da `workflow` scope yok) etkinleştirilse **bile sonuç üretmez**: bu hesapta GitHub Actions bugüne kadar hiç koşmadı — workflow'u olan iki depoda **55/55 `startup_failure`**, sıfır başarı, `workflow_dispatch` dahil. Koşum workflow dosyasına hiç ulaşmıyor (`path: BuildFailed`), yani sebep YAML değil, hesap düzeyinde (faturalandırma). Eski aktive etme reçetesi (`gh auth refresh -s workflow` + `git mv`) teknik olarak doğru ama **yeşil bir kapı vermez**; uyarı `ci/README.md`'nin başında. **Tek gerçek kapı yerel:** `python -m pytest tests/ -q` (25/25). Bu depoya `schedule:` tetikleyicisi de eklenmez.
- **RelBench adapter `rel-f1` ile DOGRULANDI** (driver-dnf AUC ~0.592, driver-position MAE ~3.61). `eval` extra'sini **izole `.venv_eval`'de** kur (cekirdek `.venv`'i bozma). Basit DFS baseline tuned RDL'in altinda — beklenen; GNN backend "SIRADAKI IS"te.
- **fraud sinyali sentetik veride zayif.** Bu yuzden return-risk, musteri seviyesinde **2-hop join** olarak reframe edildi (~0.689 ROC-AUC).
- **Windows cp1252 encoding.** Turkce konsol ciktisi icin `PYTHONUTF8=1` ayarla; kutuphane zaten `realpath._io.sprint` ile encoding-safe yazar ve CLI/eval `_io.use_utf8()` cagirir.
- **NL→PQL canli yol API key ister.** `ANTHROPIC_API_KEY` yoksa offline template fallback devreye girer (churn/forecast/fraud keyword routing). Default model `claude-sonnet-4-6`, override env `REALPATH_LLM_MODEL`.
- **Lisans karantinasi:** getML (ELv2) ve TabPFN-2.5 (ticari kullanim yasak) cekirdege ALINMAZ — yalnizca opsiyonel eklenti. Cekirdek MIT/BSD/Apache kalir.
- **`.duckdb` gitignored** — sample DB'yi her ortamda yeniden uret.

---

## 5) DOGRULAMA CHECKLIST (smoke-test)

Windows venv yorumlayicisi: `.venv\Scripts\python.exe`. Konsol Turkce icin once `set PYTHONUTF8=1`.

```bash
# 0) (gerekirse) editable kurulum
.venv\Scripts\python.exe -m pip install -e .

# 1) Sample DB'yi uret (gitignored — her ortamda yeniden)
.venv\Scripts\python.exe data\make_sample_db.py data\shop.duckdb
#   beklenen: ~1200 customers, ~14343 transactions, ~2209 returns (seed 42)

# 2) Sema
.venv\Scripts\python.exe -m realpath.cli schema --db data\shop.duckdb
#   beklenen: 4 tablo (customers/products/transactions/returns) + PK/FK/time-index

# 3) Churn tahmini (PQL)
.venv\Scripts\python.exe -m realpath.cli predict "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id" --db data\shop.duckdb --explain
#   beklenen: roc_auc ~0.749, accuracy ~0.737 + global join-path drivers

# 4) Lokal eval (relational vs baseline)
.venv\Scripts\python.exe -m realpath.eval --db data\shop.duckdb
#   beklenen: roc_auc delta ~ +0.045  (=> "relational features HELP")

# 5) Testler
.venv\Scripts\python.exe -m pytest tests\ -q
#   beklenen: 25 passed

# 6) (opsiyonel) Streamlit demo
.venv\Scripts\python.exe -m streamlit run realpath\demo_app.py
#   http://localhost:8501
```

---

## 6) KARAR GUNLUGU

Mimari ve urun kararlarinin gerekceleri: **`docs/DECISIONS.md`**.
(Henuz yoksa olustur; bu dosyadaki "BILINEN SORUNLAR" maddeleri — pandas pin, lisans karantinasi, fraud reframe — ilk girisler olmali.)
Detayli strateji & teknik doku: **`docs/REALPATH_SPEC_v2.md`**.

---

## 7) BU DOSYAYI NASIL GUNCELLERIM

1. En ustteki **"Son guncelleme"** satirini bugunun tarihi + hazirlayan ile degistir.
2. Bitirdigin isleri **TAMAMLANANLAR**'a tasi ve **SIRADAKI IS**'teki kutucugu `[x]` yap (ya da yeni madde ekle: WHAT/WHY/WHERE/ACCEPTANCE).
3. Yeni metrik / sorun / karar varsa ilgili tabloyu ve **BILINEN SORUNLAR**'i guncelle; kalici kararlar `docs/DECISIONS.md`'ye.
4. Degisikligi **lokal** commit'le (kisa, Ingilizce mesaj); `pushla` denmedikce push etme.
