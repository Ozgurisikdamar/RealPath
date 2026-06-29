# realpath.dev — SPRINTS (yürütme planı)

> **Bu dosya, "ne yapılacak"ın TEK kaynağıdır.** İş (business) ve yazılım (software) kararları
> burada **sprint**'lere bölünür. `CLAUDE.md`'deki **"devam" protokolü** bu dosyayı okur:
> **🟢 GÜNCEL** sprint'teki en üst **açık ve bloke-olmayan** görev = bir sonraki iştir.
>
> Kararların **gerekçeleri** [`DECISIONS.md`](DECISIONS.md)'de (ADR + Business Decisions).
> Canlı durum [`HANDOVER.md`](HANDOVER.md)'de. API [`API.md`](API.md)'de.
>
> **Son güncelleme:** 2026-06-19 · **Güncel sprint:** **Sprint 2 — Real RDL (Linux/CI)** · Sprint 1 ✅ **8/8 TAMAM**

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

## Sprint 1 — OSS Launch Readiness ✅ TAMAM (8/8)

**Hedef:** Projeyi *halka açık yayına hazır* hale getir — temiz paket, cilalı demo, kanıt
tablosu, ve net konumlandırma. Hepsi **bu makinede (Windows) yapılabilir.**

**Software**
- [x] **LICENSE dosyası ekle (MIT)** — repo kökü. ✅ Kök `LICENSE` (MIT, "2026 realpath.dev contributors"); pyproject/README ile tutarlı.
- [x] **Streamlit demo'ya kalibrasyon** ✅ — `demo_app.py`: "Olasılık kalibrasyonu" toggle → `predict(calibrate=True)` + `result.reliability()` caption (Brier/ECE). `AppTest` ile doğrulandı (BRIER 0.20, ECE 0.085, no-exception).
- [x] **PyPI build dry-run** ✅ — `python -m build` (wheel+sdist; `twine check` PASSED). Temiz venv'de wheel kuruldu (pandas **2.2.3** pin korundu), `realpath make-sample` + `predict` çalıştı (0.7492). **Bug bulundu+düzeltildi:** generator paket içine taşındı (`realpath/sample_data.py`) — pip kullanıcısı için `make-sample` artık çalışıyor. `dist/`,`build/` gitignore.
- [x] **`examples/quickstart.ipynb`** ✅ — connect→ask→predict→explain→forecast (14 hücre); nbclient ile baştan sona **hatasız çalıştırıldı** (8/8 kod hücresi çıktılı).
- [x] **`docs/BENCHMARKS.md`** ✅ — connector parity (0.7492 ×3), DFS-vs-baseline (+0.045), vertical
  şablonlar, kalibrasyon (ECE 0.033→0.014), RelBench adapter (rel-f1 0.592/3.61), GNN durumu — hepsi
  reprodüksiyon komutlarıyla.

**Business**
- [x] **`docs/PITCH.md`** ✅ — tek sayfa: problem → çözüm → 4 moat → "neden Kumo değil" → hedef
  kullanıcı → traction → open-core → CTA.
- [x] **Open-core sınırı kararı** ✅ — [`DECISIONS.md`](DECISIONS.md) **BD-002**'de net sınır tablosu
  (ücretsiz: çekirdek/connectors/CLI/demo · ticari: managed/warehouse/governance/destek).
- [x] **OSS launch checklist** ✅ — [`docs/LAUNCH_CHECKLIST.md`](LAUNCH_CHECKLIST.md): repo hygiene,
  kanıt/mesaj, dağıtım (PyPI), Show HN taslağı; bitenler işaretli, kalanlar Sprint 4'e devrediliyor.

---

## Sprint 2 — Real RDL (Linux/CI) 🟢 GÜNCEL

**Hedef:** GNN'i **adil, leakage-safe temporal** olarak koştur ve DFS baseline'ı geç — bunun
için Linux gerekir (`pyg-lib`). Bu makinede (Windows) **kısmen bloke**; CI/WSL'de yapılır.

- [x] **DFS baseline tuning** ✅ — `max_depth` 2→3, rel-f1/driver-dnf **0.592 → 0.658** (+0.066, 120→869 feats). `BENCHMARKS.md §5`.
- [x] **Ek RelBench görev(ler)** ✅ — `rel-f1/driver-top3` (clf) **AUC 0.769**, `driver-position` (reg) MAE 3.61. (rel-hm GB'larca indirme — `rel-f1` ile yetinildi.)
- [x] **GNN Linux CI job'u** ✅ — `.github/workflows/gnn-eval.yml` (lokal `ci` branch): ubuntu runner, torch 2.5 + `pyg-lib`+`torch-sparse` (Linux wheel) + eval extra → `eval --gnn` (adil temporal). Push `workflow` scope bekler.
- [ ] ⏸️ **BLOKE (infra)** GNN adil temporal SAYISI — Docker/Linux'ta denendi ama **bu makinenin diski %100 doldu** (torch+PyG ≈2 GB) ve Docker storage bozuldu (kod hatası değil, altyapı). Sayı **GitHub Linux CI**'da (`gnn-eval.yml`) üretilecek; `workflow`-scope'lu push + CI koşusu gerekir. Alternatif: diski boş bir Linux/WSL'de `pip install pyg-lib` + `eval --gnn`.

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
