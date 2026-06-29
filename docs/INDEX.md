# relpath.dev — Dokümantasyon Haritası (INDEX)

Bu sayfa, projedeki tüm dokümanların **giriş noktasıdır**. Ne aradığını bul, doğru dosyaya git. Her satırda bir *one-line purpose* ve *"ne zaman oku"* notu var.

> **relpath.dev** — açık kaynak, self-hostable, **local-first** ilişkisel (relational) tahmin motoru. Bir veritabanına bağlan, tahmin sorusunu düz dille veya **PQL** ile sor, **açıklamalı** bir cevap al — veriyi hiçbir yere taşımadan. Kumo.AI / KumoRFM'in açık kaynak karşılığı.

> **Path notu:** Sadece `CLAUDE.md`, `README.md` ve `CONTRIBUTING.md` repo **kökünde** durur. Geri kalan tüm dokümanlar `docs/` altındadır (`docs/HANDOVER.md`, `docs/ARCHITECTURE.md` …). Aşağıda hepsi `docs/`-prefix'li yazılır.

---

## Önce bunu oku: oturum başlangıç sırası

Yeni bir oturuma (session) başlayan herkesin **tavsiye edilen okuma sırası**:

1. **`CLAUDE.md`** (repo kökü) — operating manual + "devam-et" protokolü. **Her zaman ilk burası.**
2. **`docs/SPRINTS.md`** — 🟢 güncel sprint; **DEVAM buradan başlar** (backlog'un tek kaynağı).
3. **`docs/HANDOVER.md`** — projenin **canlı durumu** (ne bitti, bilinen sorunlar, doğrulama).
4. Gerisi **ihtiyaç oldukça**: API için `docs/API.md`, derin teknik için `docs/ARCHITECTURE.md`, reçeteler için `docs/SKILLS.md`, neden-böyle için `docs/DECISIONS.md`, strateji için `docs/RELPATH_SPEC_v2.md`.

---

## Doküman tablosu

| Doküman | Amaç (tek satır) | Ne zaman oku |
|---|---|---|
| **`CLAUDE.md`** (kök) | Operating manual + golden rules + devam-et protokolü | **Her oturumun ilk dosyası.** Kuralları (push yok, pandas pin, vb.) hatırlamak için |
| **`docs/SPRINTS.md`** | 🟢 Güncel sprint + plan; **DEVAM buradan başlar** | İkinci dosya. "Sırada ne var?" — backlog'un tek kaynağı |
| **`docs/HANDOVER.md`** | **Canlı durum** + bilinen sorunlar + doğrulama checklist | "Nerede kaldık, ne bitti?" |
| **`docs/ARCHITECTURE.md`** | Derin teknik: modüller, data-flow, tasarım | Bir modülü değiştirmeden / yeni özellik eklemeden önce |
| **`docs/API.md`** | Python / CLI / PQL API referansı | "Hangi fonksiyon / komut / parametre var?" |
| **`docs/SKILLS.md`** | Reçeteler (recipes): sık yapılan işlerin komutları | "Şunu nasıl çalıştırırım?" derken |
| **`docs/ROADMAP.md`** | Fazlara bölünmüş plan (Phase-1/2…) | Önceliklendirme ve "bu iş roadmap'te nerede?" için |
| **`docs/DECISIONS.md`** | ADR'ler — mimari kararlar ve gerekçeleri | "Neden DuckDB / neden pandas 2.2.x?" gibi sorularda |
| **`docs/RELPATH_SPEC_v2.md`** (+ `.docx` / `.html`) | Strateji & teknik spec (v2) | Ürün konumlandırması ve vizyon bağlamı gerektiğinde |
| **`README.md`** (kök) | İki dilli (TR/EN) quickstart | İlk kurulum / dışarıya tanıtım / hızlı demo |
| **`CONTRIBUTING.md`** (kök) | Geliştirici kurulum + katkı kuralları + guardrail'ler | Dış katkı / yeni geliştirici onboarding |
| **`docs/BENCHMARKS.md`** | Doğrulanmış sayılar + reprodüksiyon | "Hangi metrik ne, nasıl üretilir?" |
| **`docs/PITCH.md`** | Tek sayfa konumlandırma (business) | Dışarıya tanıtım / yatırımcı / launch |
| **`docs/LAUNCH_CHECKLIST.md`** | OSS yayın öncesi checklist | Halka açık launch hazırlığında |
| **`docs/logo.svg` · `docs/logo.png`** | Proje logosu (varlık) | README / demo / sunum görselleri için |

---

## Golden / non-negotiable kurallar (özet — tamamı `CLAUDE.md`'de)

Bunlar **her oturumda** geçerlidir; detay ve istisnalar için `CLAUDE.md`.

- **Push yok.** Kullanıcı açıkça **"pushla"** demeden `git push` / PR / merge **yapma**. Lokal commit OK, **iş bitiminde** atılır.
- **Commit kimliği** global gitconfig'ten gelir (author: Ozgur Isik Damar, GitHub no-reply). **Asla** `Co-Authored-By: Claude` veya Claude trailer ekleme. Mesajlar kısa, insanca, **İngilizce**.
- **pandas 2.2.x'te sabit** (pin politikası `2.2.3`). pandas 3.0 woodwork'ü kırar (`.ww` accessor şeması kalıcı olmaz → Featuretools EntitySet build patlar). **Yükseltme.** Not: `pyproject.toml` daha gevşek `pandas>=2.0` ister — gerçek pin (`2.2.3`) bu spec'ten daha sıkıdır; çalışırken `2.2.x`'te kal.
- **Core deps permissive** (MIT/BSD/Apache) kalır. getML (ELv2) ve TabPFN-2.5 (non-commercial) **karantinada** — yalnız optional/plugin, asla core değil.
- **NL→PQL** için `ANTHROPIC_API_KEY` gerekir (Claude yolu); yoksa **offline template fallback** devreye girer. Varsayılan model `claude-sonnet-4-6` (env `RELPATH_LLM_MODEL` ile override).
- **Local-first** ürün tezidir: veri makineden çıkmak zorunda olmamalı. **DuckDB varsayılan** kalır.
- **Windows'ta** `PYTHONUTF8=1` tercih et (ya da `relpath._io.sprint`'e güven) — Türkçe metin cp1252 konsolunu çökertmesin.

---

## Hızlı komut referansı

İlk kurulum — proje `requires-python = ">=3.10"`; lokal `.venv` interpreter'ı Python **3.11**:

```powershell
.venv\Scripts\python.exe -m pip install -e .
```

Örnek veritabanını üret (gitignore'da — yeniden üretilir):

```powershell
.venv\Scripts\python.exe data\make_sample_db.py data\shop.duckdb
```

Çekirdek akış (CLI entry point: `relpath` veya `python -m relpath.cli`). Köşeli parantezler opsiyonel flag'ler, `--db` zorunlu:

```powershell
relpath make-sample [--out data\shop.duckdb]
relpath schema  --db data\shop.duckdb
relpath ask     "churn edecek musteriler" --db data\shop.duckdb
relpath predict "<PQL ya da düz soru>" --db data\shop.duckdb [--top 10] [--explain] [--no-eval] [--csv out.csv]
relpath eval    [--db data\shop.duckdb] [--pql "<PQL>"] [--dataset <RelBench>] [--task <task>]
```

Testler ve eval modülü:

```powershell
.venv\Scripts\python.exe -m pytest tests\ -q          # 25/25 pass
.venv\Scripts\python.exe -m relpath.eval              # [--db --pql --dataset --task --max-depth (vars. 2)]
```

Demo (Streamlit, varsayılan port 8501):

```powershell
streamlit run relpath\demo_app.py
```

> Türkçe konsol çıktısı için: `set PYTHONUTF8=1` (CLI/eval zaten `_io.use_utf8()` çağırır).
> Not: `relpath eval` CLI subcommand'ında `--max-depth` **yok**; bu flag yalnız `python -m relpath.eval` modül girişinde var.

---

## 30 saniyede mimari

Tek cümlelik data-flow — detay `docs/ARCHITECTURE.md`'de:

```
connect (DuckDB)
  -> schema (FK graph, time index)
  -> PQL compile (join inference + temporal window isolation)
  -> features (Featuretools DFS + cutoff_time = leakage-safe)
  -> model (LightGBM / opsiyonel TabPFN)
  -> explain (join-path provenance, opsiyonel SHAP)
```

**PQL grameri** (tek satır):

```
PREDICT AGG(table.col|*, start, end, unit) [op value]
  FOR EACH entity_table.primary_key [WHERE filter] [ASSUMING filter]
```

AGG ∈ {COUNT, SUM, AVG, MIN, MAX} · unit ∈ {days, weeks, months} · op ∈ {==, !=, >, >=, <, <=}. Comparison varsa **classification**, yoksa **regression**. `WHERE` = label'a sayılan target satırlarını süzer; `ASSUMING` = hangi entity'lerin skorlanacağını kısıtlar.

**Doğrulanmış metrikler** (sample DB): churn ROC-AUC ~0.749 / accuracy ~0.737 (entity-only baseline ROC-AUC ~0.704, Δ +0.045) · customer-level return-risk (2-hop join) ~0.689 ROC-AUC · product demand forecast (varsayılan 3 ay) MAE ~8.4 (bu sentetik veride ilişkisel lift yok; churn asıl gösterge). Testler: **25/25 pass**.

---

## "Read when…" hızlı eşleme

- Yeni başlıyorum / her oturum → **`CLAUDE.md`** → **`docs/HANDOVER.md`**
- Kod değiştireceğim → **`docs/ARCHITECTURE.md`**
- Komut/işlem hatırlamam lazım → **`docs/SKILLS.md`** (ya da yukarıdaki komut referansı)
- Sıradaki iş ne / öncelik → **`docs/ROADMAP.md`** + **`docs/HANDOVER.md`**
- "Neden böyle yapılmış?" → **`docs/DECISIONS.md`**
- Strateji / konumlandırma → **`docs/RELPATH_SPEC_v2.md`**
- Dışarıya göstereceğim / hızlı kurulum → **`README.md`**
