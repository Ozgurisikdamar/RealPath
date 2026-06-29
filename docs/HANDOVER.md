# HANDOVER — relpath.dev

> **Son guncelleme: 2026-06-19 — hazirlayan: Claude (Opus 4.8)** · son is: Postgres connector (docker `postgres:16` ile uçtan-uca doğrulandı, churn 0.7492) + CONTRIBUTING.
> Bu bir *living* state dosyasidir. **Her session** commit'ten ONCE bu satiri ve asagidaki checklist'leri guncelle.
> `devam et` dendiginde once bu dosya okunur; "SIRADAKI IS" listesindeki en ust kutucuk bir sonraki istir.

**relpath.dev** — acik kaynak, self-host, **local-first** relational prediction engine. Bir veritabani baglarsin, tahmin sorusunu duz dil veya PQL ile sorarsin, **aciklamali** bir cevap alirsin — veri makineden cikmadan. Kategori lideri **Kumo.AI / KumoRFM**'in acik-kaynak karsiti.

---

## 1) SU ANKI DURUM

**Phase 1 PoC tamamlandi.** Calisan ve dogrulanmis bir uctan-uca hat var:

- **connect → schema (FK grafigi) → PQL compile (join inference + temporal window izolasyonu) → features (DFS + cutoff_time) → model (LightGBM/TabPFN) → explain (join-path provenance)**
- **Dikey sablonlar:** `churn`, `forecast`, `fraud` (fraud, sentetik veride zayif sinyal — asagi bak).
- **NL → PQL:** Claude (anthropic SDK) yolu + API key yoksa **offline deterministik sablon fallback** (churn/forecast/fraud keyword routing, TR+EN). Cikti her zaman tekrar-parse edilerek dogrulanir.
- **Aciklanabilirlik:** global importance + per-entity join-path karti (SHAP varsa, yoksa LightGBM gain fallback).
- **Eval:** `evaluate_local()` relpath full relational feature'lari ile entity-only baseline'i karsilastirir.
- **Testler:** 23/23 gecer. `test_leakage.py` gelecek-sizintisi olmadigini, anchor sonrasi tum satirlari silip feature matrix'in ayni kaldigini gostererek **kanitlar**; ayrica label penceresinin kesin olarak gelecekte oldugunu dogrular.

### Dogrulanmis metrikler (sample DB uzerinde)

| Gorev | Metrik | Deger | Not |
|---|---|---|---|
| Churn (classification) | ROC-AUC | **~0.749** | entity-only baseline ~0.704, delta **+0.045** |
| Customer return-risk (2-hop join) | ROC-AUC | **~0.689** | musteri seviyesine reframe edildi |
| Product demand forecast (varsayılan 3 ay `SUM(quantity)`) | MAE | **~8.41** (rmse ~10.1) | ilişkisel lift YOK (baseline ~7.48); 2 ay varyant ~6.75. **Churn asıl gösterge.** |
| Test suite | pytest | **23/23 pass** | |

### Git durumu

- Git repo, branch `master`, **remote `origin` → github.com/Ozgurisikdamar/relpath (private)**, push edildi.
- **KURAL:** kullanici `pushla` (ya da `push`) DEMEDIKCE push / PR / merge YOK. Lokal commit serbest, is bitiminde. (Bu turda kullanici "pushla" dedigi icin pushlandi.)

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
- [x] CLI (`cli.py`): `make-sample / schema / ask / predict / eval`, entry point `relpath`.
- [x] Streamlit demo (`demo_app.py`, port 8501, Turkce UI).
- [x] Sentetik e-ticaret DB generator (`data/make_sample_db.py`, 4 tablo, seed 42).
- [x] Encoding-safe I/O (`_io.py`: `sprint`, `use_utf8`).
- [x] Testler: `test_pql_parser.py` (10), `test_leakage.py` (2), `test_templates.py` (8), `test_calibration.py` (3: AUC korunur, ECE düşer, e2e), `conftest.py` (sample_db + engine fixtures) — **23/23**.
- [x] Bilingual README (TR/EN) + `docs/RELPATH_SPEC_v2.md` (+ .docx/.html) + logo.
- [x] CI + paketleme: `.github/workflows/ci.yml` (push/PR'da ruff + pytest, py3.10/3.11), `pyproject` metadata (`[project.urls]`, classifiers, **pandas pin `>=2.0,<2.3`**), `[tool.ruff]` + lint temiz. Temiz-oda kurulumla (`pip install -e ".[dev]"`) dogrulandi: pandas 2.2.3.
- [x] GitHub'a push: **private** repo `Ozgurisikdamar/relpath` (origin/master). NOT: `ci.yml` commit'i token'da `workflow` scope olmadigi icin **pushlanmadi** (lokalde bekliyor; `gh auth refresh -h github.com -s workflow` sonrasi pushlanir).
- [x] Per-entity probability **calibration** (opt-in isotonic): `model.py` (`fit_model(calibrate=)`, `reliability()` Brier+ECE), `engine.predict(calibrate=)`, `result.reliability()`. Doğrulandı: ECE 0.033→0.014, AUC korunur; **default kapalı** (headline 0.749 değişmedi).
- [x] **Postgres connector**: `connect.py` `PostgresBackend` + `open_backend` `postgres://` yolu + `postgres` extra (`psycopg`). `?`→`%s` çevirisi, `public` şema introspection. **Docker `postgres:16` ile UÇTAN-UCA DOĞRULANDI**: şema/FK çıkarımı + churn ROC-AUC **0.7492** (DuckDB ile birebir aynı). `data/load_postgres.py` yükleyici, `tests/test_postgres.py` (`RELPATH_TEST_PG` yoksa skip).

---

## 3) SIRADAKI IS (oncelik sirali)

> Her madde: **WHAT / WHY / WHERE / ACCEPTANCE**. En ust **AKTIF** (isaretsiz, bloke olmayan) kutu = bir sonraki is.
> `⏸️ BLOKE` etiketli maddeyi atla (dis bir sey bekliyor); ilk aktif maddeden devam et.

- [ ] ⏸️ **BLOKE** — **Canli Claude NL→PQL yolunu API key ile dogrula** (env'de `ANTHROPIC_API_KEY` YOK; kullanici saglayana kadar atla, sonraki aktif madde = Postgres connector)
  - WHAT: Gercek `ANTHROPIC_API_KEY` ile `nl_to_pql`'in Claude yolunu (offline fallback degil) calistir.
  - WHY: Su an sadece offline template fallback dogrulandi; canli yol untested.
  - WHERE: `relpath/nlp.py` (`nl_to_pql`, `source` alani), env `ANTHROPIC_API_KEY`, `RELPATH_LLM_MODEL` (default `claude-sonnet-4-6`).
  - ACCEPTANCE: `relpath ask "hangi musteriler iade yapacak" --db data/shop.duckdb` gecerli PQL dondurur ve `NLResult.source` Claude yolunu (offline degil) gosterir.

- [ ] **RelBench adapter'i eval extra ile calistir/dogrula**
  - WHAT: `relbench_adapter.run_relbench_task`'i gercek bir RelBench task'inda kosturup feature/model yeniden-kullanimini dogrula.
  - WHY: Modul bu ortamda **hic calistirilmadi** (untested); torch+relbench kurulu degil.
  - WHERE: `relpath/relbench_adapter.py`, `relpath/eval.py` (`evaluate_relbench`), extra: `pip install -e ".[eval]"`.
  - ACCEPTANCE: `python -m relpath.eval --dataset rel-hm --task user-churn` bir metrik tablosu uretir; hatalar duzeltilir; sonuc bu dosyaya yazilir.

- [ ] **CONTRIBUTING guide yaz**
  - WHAT: Kurulum, test calistirma, kod stili (ruff), commit kurallari, sizinti-guvenligi prensibi.
  - WHY: Dis katki icin onkosul.
  - WHERE: yeni `CONTRIBUTING.md`, `docs/DECISIONS.md`'ye atif.
  - ACCEPTANCE: Yeni bir gelistirici dosyayi takip ederek env kurup `python -m pytest tests/ -q` calistirabilir.

---

## 4) BILINEN SORUNLAR / DIKKAT

- **pandas 3.0 KIRIYOR.** `pandas==2.2.x` (pinli **2.2.3**) sart. pandas 3.0'da `.ww` woodwork accessor semasi kalici olmuyor → Featuretools EntitySet build cokuyor. **Yukseltme.**
- **`relbench_adapter.py` bu ortamda calistirilmadi (untested).** torch+relbench (`[eval]` extra) kurulu degil; dogrulama "SIRADAKI IS"te.
- **fraud sinyali sentetik veride zayif.** Bu yuzden return-risk, musteri seviyesinde **2-hop join** olarak reframe edildi (~0.689 ROC-AUC).
- **Windows cp1252 encoding.** Turkce konsol ciktisi icin `PYTHONUTF8=1` ayarla; kutuphane zaten `relpath._io.sprint` ile encoding-safe yazar ve CLI/eval `_io.use_utf8()` cagirir.
- **NL→PQL canli yol API key ister.** `ANTHROPIC_API_KEY` yoksa offline template fallback devreye girer (churn/forecast/fraud keyword routing). Default model `claude-sonnet-4-6`, override env `RELPATH_LLM_MODEL`.
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
.venv\Scripts\python.exe -m relpath.cli schema --db data\shop.duckdb
#   beklenen: 4 tablo (customers/products/transactions/returns) + PK/FK/time-index

# 3) Churn tahmini (PQL)
.venv\Scripts\python.exe -m relpath.cli predict "PREDICT COUNT(transactions.*, 0, 30, days) == 0 FOR EACH customers.customer_id" --db data\shop.duckdb --explain
#   beklenen: roc_auc ~0.749, accuracy ~0.737 + global join-path drivers

# 4) Lokal eval (relational vs baseline)
.venv\Scripts\python.exe -m relpath.eval --db data\shop.duckdb
#   beklenen: roc_auc delta ~ +0.045  (=> "relational features HELP")

# 5) Testler
.venv\Scripts\python.exe -m pytest tests\ -q
#   beklenen: 23 passed

# 6) (opsiyonel) Streamlit demo
.venv\Scripts\python.exe -m streamlit run relpath\demo_app.py
#   http://localhost:8501
```

---

## 6) KARAR GUNLUGU

Mimari ve urun kararlarinin gerekceleri: **`docs/DECISIONS.md`**.
(Henuz yoksa olustur; bu dosyadaki "BILINEN SORUNLAR" maddeleri — pandas pin, lisans karantinasi, fraud reframe — ilk girisler olmali.)
Detayli strateji & teknik doku: **`docs/RELPATH_SPEC_v2.md`**.

---

## 7) BU DOSYAYI NASIL GUNCELLERIM

1. En ustteki **"Son guncelleme"** satirini bugunun tarihi + hazirlayan ile degistir.
2. Bitirdigin isleri **TAMAMLANANLAR**'a tasi ve **SIRADAKI IS**'teki kutucugu `[x]` yap (ya da yeni madde ekle: WHAT/WHY/WHERE/ACCEPTANCE).
3. Yeni metrik / sorun / karar varsa ilgili tabloyu ve **BILINEN SORUNLAR**'i guncelle; kalici kararlar `docs/DECISIONS.md`'ye.
4. Degisikligi **lokal** commit'le (kisa, Ingilizce mesaj); `pushla` denmedikce push etme.
