# relpath.dev — SPRINTS (yürütme planı)

> **Bu dosya, "ne yapılacak"ın TEK kaynağıdır.** İş (business) ve yazılım (software) kararları
> burada **sprint**'lere bölünür. `CLAUDE.md`'deki **"devam" protokolü** bu dosyayı okur:
> **🟢 GÜNCEL** sprint'teki en üst **açık ve bloke-olmayan** görev = bir sonraki iştir.
>
> Kararların **gerekçeleri** [`DECISIONS.md`](DECISIONS.md)'de (ADR + Business Decisions).
> Canlı durum [`HANDOVER.md`](HANDOVER.md)'de. API [`API.md`](API.md)'de.
>
> **Son güncelleme:** 2026-06-19 · **Güncel sprint:** **Sprint 1 — OSS Launch Readiness** (2/7: LICENSE, demo kalibrasyon)

---

## Sprint nasıl işler

- Her sprint = tutarlı bir **hedef** + business/software görevleri (checkbox).
- Her görev: **WHAT** + **ACCEPTANCE** (nasıl "bitti" denir).
- Etiketler: `[ ]` açık · `[x]` bitti · `⏸️ BLOKE` (dış girdi bekler — atla).
- **"devam"** dendiğinde: güncel sprint → ilk açık & bloke-olmayan görevi al → yap →
  `[x]` işaretle → HANDOVER'ı güncelle → lokal commit (**push YOK**, "pushla" bekler).
- Sprint'in tüm açık (bloke olmayan) görevleri bitince: bir sonraki sprint'i **🟢 GÜNCEL**
  yap, bu satırı ve `HANDOVER` "son güncelleme"yi güncelle.

---

## Sprint 0 — Foundation & Validation ✅ TAMAM

**Hedef:** Çalışan, doğrulanmış, dokümante PoC. *(Tüm görevler bitti — tarihçe için burada.)*

- [x] Uçtan uca motor: connect → schema (FK) → PQL → DFS (cutoff) → LightGBM → explain.
- [x] **3 backend** doğrulandı (DuckDB / Postgres / MySQL) — hepsi churn ROC-AUC **0.7492**.
- [x] Dikey şablonlar (churn/forecast/fraud) + NL→PQL (offline fallback) + açıklanabilirlik.
- [x] Opt-in kalibrasyon (isotonic; ECE 0.033→0.014) + CLI `--calibrate`.
- [x] RelBench adapter `rel-f1` ile doğrulandı; RDL/GNN backend **implementasyonu** (kod doğrulandı).
- [x] **25/25 test** (+2 skip), ruff temiz, GitHub Actions CI, paketleme, tam doküman seti.

> Detay: [`HANDOVER.md`](HANDOVER.md) "Tamamlananlar".

---

## Sprint 1 — OSS Launch Readiness 🟢 GÜNCEL

**Hedef:** Projeyi *halka açık yayına hazır* hale getir — temiz paket, cilalı demo, kanıt
tablosu, ve net konumlandırma. Hepsi **bu makinede (Windows) yapılabilir.**

**Software**
- [x] **LICENSE dosyası ekle (MIT)** — repo kökü. ✅ Kök `LICENSE` (MIT, "2026 relpath.dev contributors"); pyproject/README ile tutarlı.
- [x] **Streamlit demo'ya kalibrasyon** ✅ — `demo_app.py`: "Olasılık kalibrasyonu" toggle → `predict(calibrate=True)` + `result.reliability()` caption (Brier/ECE). `AppTest` ile doğrulandı (BRIER 0.20, ECE 0.085, no-exception).
- [ ] **PyPI build dry-run** — paketleme sağlığı.
  - WHAT: `python -m build` → sdist+wheel; temiz venv'de `pip install dist/*.whl` → `import relpath`.
  - ACCEPTANCE: Wheel temiz kurulur, `relpath` CLI çalışır; (yayın değil, sadece doğrulama).
- [ ] **`examples/quickstart.ipynb`** — notebook.
  - WHAT: connect → ask → predict → explain → forecast; çıktılı hücreler.
  - ACCEPTANCE: Notebook baştan sona hatasız çalışır (nbconvert --execute).
- [ ] **`docs/BENCHMARKS.md`** — kanıt tablosu.
  - WHAT: Connector parity (DuckDB/PG/MySQL=0.7492), DFS-vs-baseline (+0.045), RelBench adapter
    (rel-f1 driver-dnf 0.592 / driver-position MAE 3.61), GNN durumu (kod doğrulandı, temporal bloke).
  - ACCEPTANCE: Tek tabloda tüm doğrulanmış sayılar + nasıl yeniden üretilir.

**Business**
- [ ] **`docs/PITCH.md`** — tek sayfa konumlandırma.
  - WHAT: Problem → çözüm → 4 moat → "neden Kumo değil" → hedef kullanıcı → CTA. SPEC'in özeti.
  - ACCEPTANCE: 1 sayfa, dışarıya gösterilebilir; SPEC ile tutarlı.
- [ ] **Open-core sınırı kararı** → [`DECISIONS.md`](DECISIONS.md) BD-002'yi netleştir.
  - WHAT: Neyin ücretsiz (çekirdek, connectors, CLI/demo) / neyin ticari (managed, warehouse
    konnektörleri, destek) olduğunu yaz.
  - ACCEPTANCE: DECISIONS'ta net bir sınır tablosu; SPRINTS sonraki sprint'lerle tutarlı.
- [ ] **OSS launch checklist** (bu sprint sonunda) — README rozetleri, topics, CONTRIBUTING (var),
  CODE_OF_CONDUCT (opsiyonel), "Show HN" taslağı.

---

## Sprint 2 — Real RDL (Linux/CI) ⏭️

**Hedef:** GNN'i **adil, leakage-safe temporal** olarak koştur ve DFS baseline'ı geç — bunun
için Linux gerekir (`pyg-lib`). Bu makinede (Windows) **kısmen bloke**; CI/WSL'de yapılır.

- [ ] ⏸️ **BLOKE (Windows)** GNN temporal benchmark — `temporal=True` Linux/WSL'de; rel-f1'de DFS'i geç.
- [ ] GNN için Linux CI job'u (eval extra + pyg-lib) — sonuç leaderboard tablosuna.
- [ ] RelBench v2'de 1-2 ek görev (rel-hm churn) — adapter + GNN karşılaştırması.
- [ ] DFS baseline'ı iyileştir (depth/primitive tuning) — rel-f1'de 0.59'u yükselt.

---

## Sprint 3 — Connectors & Warehouse ⏭️

**Hedef:** Kurumsal veri kaynaklarına aç; open-core'un ticari katmanını şekillendir.

- [ ] Snowflake **read** connector (BackendInterface) — `snowflake://`.
- [ ] BigQuery read connector — `bigquery://`.
- [ ] Büyük-ölçek doğrulama (çok-milyon satır) + bellek/performans notları.
- [ ] Warehouse "zero-data-movement" hikâyesi (DuckDB ATTACH / push-down) — DECISIONS'a.

---

## Sprint 4 — Product Surface & GTM ⏭️

**Hedef:** Geliştirici deneyimi + pazara çıkış.

- [ ] ⏸️ **BLOKE (API key)** Canlı Claude NL→PQL doğrula (`ANTHROPIC_API_KEY`).
- [ ] Hosted demo (Streamlit Cloud / HF Spaces) — NL→PQL lead-magnet.
- [ ] MCP / agent arayüzü (`predict` skill) — Kumo'nun MCP'sine açık-kaynak yanıt.
- [ ] Dikey içerik/SEO (churn/forecast/fraud) + 1-tık şablon galerisi.

---

## Icebox (henüz sprint değil)

- Relational Foundation Model (in-context, zero-train) — vizyon (SPEC §1.3).
- Streaming / real-time skorlama. · Multimodal (metin sütunları, text embedder).
- Nedensel/denetlenebilir açıklanabilirlik. · Belirsizlik/uncertainty bantları.

---

> Sprint'leri/öncelikleri değiştirmek serbest — ama **business kararları** DECISIONS BD-xxx'e,
> **teknik kararlar** ADR'a yazılır ki gerekçe kaybolmasın.
