# relpath.dev — Mimari Karar Kayıtları (DECISIONS.md)

> **Architecture Decision Records (ADR)** — *neyi neden seçtik.*
> Bu dosya, projedeki temel mühendislik kararlarının **kalıcı kaydıdır.** Amaç: bir kararı
> bir kez verip gerekçesini yazmak, böylece her session'da yeniden tartışılmasın
> (no re-litigation). Bir kararı değiştirmek isteyen biri, önce ilgili ADR'ı okumalı ve
> yeni bir ADR ile **Supersedes** ilişkisi kurmalıdır.
>
> **Tarih:** 2026-06-19 · **Sürüm:** relpath 0.1.0 · **Konum:** *open-source, self-hostable,
> local-first relational prediction engine* — Kumo.AI / KumoRFM'in açık kaynak karşıtı.

---

## ADR formatı

Her kayıt dört bölümden oluşur:

- **Context** — kararı zorunlu kılan durum/kısıt.
- **Decision** — ne yapmaya karar verdik.
- **Consequences** — sonuçlar (artı/eksi, takas, bakım yükü).
- **Status** — `Accepted` · `Proposed` · `Superseded by ADR-NNN` · `Deprecated`.

## ADR endeksi

| # | Karar | Status |
|---|---|---|
| [ADR-001](#adr-001) | pandas 2.2.x'e sabitlendi (woodwork, pandas 3.0 ile uyumsuz) | Accepted |
| [ADR-002](#adr-002) | Önce DFS + gradient boosting baseline; GNN sonra | Accepted |
| [ADR-003](#adr-003) | Local-first DuckDB'yi varsayılan ve moat yap | Accepted |
| [ADR-004](#adr-004) | v1 PQL gramerini koru; filtreleri sqlglot ile parse et | Accepted |
| [ADR-005](#adr-005) | Sızıntı güvenliği: Featuretools `cutoff_time` + truncation-eşitlik testi | Accepted |
| [ADR-006](#adr-006) | Açıklanabilirlik: DFS öznitelik-adı provenance (embedding değil) | Accepted |
| [ADR-007](#adr-007) | NL→PQL: pluggable LLM (Claude varsayılan) + offline şablon fallback | Accepted |
| [ADR-008](#adr-008) | Çekirdek lisansı MIT/BSD/Apache; getML & TabPFN-2.5 karantinada | Accepted |
| [ADR-009](#adr-009) | Şema/ilişki modeli için Featuretools EntitySet'i yeniden kullan | Accepted |
| [ADR-010](#adr-010) | PK/FK/time-index için heuristik çıkarım | Accepted |

---

<a id="adr-001"></a>
## ADR-001 — pandas 2.2.x'e sabitlendi (woodwork, pandas 3.0 ile uyumsuz)

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
Featuretools, EntitySet şemasını (logical types, semantic tags) **woodwork**'ün `.ww`
DataFrame accessor'ı üzerinden tutar. pandas 3.0 ile birlikte accessor davranışı değişti:
`.ww` şeması artık operasyonlar arasında **kalıcı olmuyor** (does not persist). Bu durumda
`build_entityset()` (`schema.py`) ve `synthesize()` (`features.py`) içindeki DFS adımı
çalışmıyor — EntitySet kurulumu sessizce veya hatayla bozuluyor. `_normalize_dtypes()`
DuckDB çıktısını `datetime64[ns]` ve `object`'e indirgese bile, woodwork şemayı
saklayamayınca ardışık `ft.dfs` çağrısı başarısız oluyor.

### Decision
`pyproject.toml` çekirdek bağımlılığı `pandas>=2.0` olarak ilan edilse de, **kurulu ortam
pandas'ı 2.2.x'e (pin: 2.2.3) sabitler.** pandas 3.0'a **yükseltilmez.** Bu, GOLDEN kural
olarak her session için bağlayıcıdır.

### Consequences
- (+) Featuretools/woodwork/DFS hattı deterministik biçimde çalışır; 25/25 test geçer.
- (−) pandas 3.0'ın performans/API kazanımlarından şimdilik feragat edilir.
- (−) Bir bağımlılık yükseltmesi sırasında bu pin yanlışlıkla kalkarsa DFS bozulur —
  bu yüzden pin hem kuralda hem burada belgelenmiştir.
- **İzleme:** woodwork pandas 3.0 uyumlu bir sürüm yayınladığında bu ADR yeniden ele alınır.

```bash
# Doğru çekirdek kurulum (Windows, .venv aktif)
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m pip show pandas   # 2.2.3 olmalı — 3.x GÖRÜRSEN DÜZELT
```

---

<a id="adr-002"></a>
## ADR-002 — Önce DFS + gradient boosting baseline; GNN sonra (80/20)

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
İlk doküman (v1) "önce GNN / Relational Foundation Model" diyordu — en pahalı, en yüksek
GPU maliyetli yol. Oysa **getml-relbench** karşılaştırması, propositionalization (DFS/FastProp)
+ gradient boosting'in birçok RelBench görevinde GNN/RDL'i **eşitlediğini ya da geçtiğini**
gösteriyor (örn. rel-amazon item-churn 0.831 vs 0.828; rel-hm user-churn 0.703 vs 0.699;
rel-hm item-sales MAE 0.031 vs 0.056 — düşük=iyi). GNN'in net üstünlüğü esas olarak
link-prediction / öneri ve derin çok-hop zamansal sinyalde.

### Decision
Faz 1 motoru **Deep Feature Synthesis (Featuretools DFS) + gradient boosting (LightGBM)**
üzerine kurulur. `features.synthesize()` `ft.dfs`'i `cutoff_time` ile çağırır
(AGG: count/sum/mean/max/min/std/num_unique; TRANS: month/weekday); `model.fit_model()`
göreve göre `LGBMClassifier`/`LGBMRegressor` seçer. GNN/RDL backend Faz 2'ye, foundation
model Faz 3'e bırakılır — **vitrin değil, yol haritası.**

### Consequences
- (+) CPU'da, local-first çalışır; GPU gerektirmez — açık kaynak/self-host konumunun temeli.
- (+) Görev-başına hızlı eğitim; doğrulanmış metrikler (churn ROC-AUC ~0.749, return-risk
  2-hop ~0.689, forecast 3 ay MAE ~8.4 — sample DB).
- (+) DFS öznitelikleri açıklanabilir (bkz. ADR-006) — baseline seçimi explainability'yi bedava verir.
- (−) Link-prediction / öneri görevlerinde tavan, GNN'den düşük olabilir — bu görevler Faz 2 kapsamına alındı.

---

<a id="adr-003"></a>
## ADR-003 — Local-first DuckDB'yi varsayılan ve moat yap

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
Kumo.AI iş modeli kapalı SaaS + Snowflake/Databricks warehouse kilidine dayanır; veri,
satıcı ekosistemine bağlı kalır. Düzenlemeli sektörler (sağlık, kamu, finans), KOBİ'ler ve
air-gapped ortamlar "veri makineden çıkamaz" kısıtıyla yaşar. Bu, Kumo'nun **yapısal olarak
giremediği** bir köşe (pazar haritasında sağ-üst: açık kaynak/self-host + otomatik ilişkisel tahmin).

### Decision
Varsayılan ve birinci-sınıf backend **DuckDB**'dir (`connect.DuckDBBackend`). Ürün tezi
**local-first:** veri hiçbir buluta/SaaS'a gitmez — relpath verinin *yanında* çalışır.
Postgres/MySQL bağlantı URL'leri şimdilik `NotImplementedError` verir (Faz 2 yol haritası);
warehouse bağlantısı bir **opsiyon**, asla zorunluluk değildir.

### Consequences
- (+) İnternet/hesap/warehouse gerektirmeden tek `pip install` ile çalışır.
- (+) Air-gapped ve "veri çıkamaz" politikalı kurumlara doğal uyum; net farklılaşma.
- (−) Postgres/MySQL/warehouse desteği ertelendi — Phase-2'de eklenecek.
- **Kural:** Local-first ürün tezi olduğundan DuckDB varsayılan kalır; veri makineden çıkmaya zorlanmaz.

---

<a id="adr-004"></a>
## ADR-004 — v1 PQL gramerini koru; filtreleri sqlglot ile parse et

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
v1, PQL'i (Predictive Query Language) deklaratif arayüz olarak tanımlamıştı. Gramer baştan
yazılırsa hem geriye uyum (v1 örnekleri, dokümantasyon) bozulur hem de WHERE/ASSUMING filtre
ifadelerini doğru ayrıştırmak için elle SQL parser yazmak gerekir — hataya açık ve gereksiz.

### Decision
v1 PQL grameri **korunur** (netleştirilerek). Şekil:

```
PREDICT AGG(table.col|*, start, end, unit) [op value]
FOR EACH entity_table.primary_key
[WHERE filter] [ASSUMING filter]
```

- `AGG ∈ {COUNT, SUM, AVG, MIN, MAX}` (MEAN → AVG alias) · `unit ∈ {days, weeks, months}`
  · `op ∈ {==, !=, >, >=, <, <=}`.
- `op` varsa **classification**, yoksa **regression** (`PredictiveTask.task_type`).
- `WHERE`: etikete sayılan hedef satırları filtreler. `ASSUMING`: skorlanacak entity evrenini daraltır.

`parse_pql()` (`pql/parser.py`) regex tabanlı gramerle iskeleti çıkarır; **WHERE/ASSUMING
filtre ifadeleri sqlglot ile parse edilir.** Geçersiz girdi `PQLSyntaxError` verir.

### Consequences
- (+) v1 ile geriye uyum; öğrenme bariyeri korunur.
- (+) Filtre ayrıştırma olgun bir SQL parser'a (sqlglot, MIT) devredilir — daha az hata, daha az bakım.
- (−) Gramer regex + sqlglot karışımı; tam SQL ifade gücü değil (bilinçli kısıt).

---

<a id="adr-005"></a>
## ADR-005 — Sızıntı güvenliği: Featuretools `cutoff_time` + truncation-eşitlik testi

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
İlişkisel tahminde en sinsi hata **label leakage:** modelin gelecekteki satırları görerek
eğitilmesi. Akademi bunu RDL'in açık problemlerinden sayar; çoğu sistem ad-hoc çözer.
"Sızıntı yok" bir slogan değil, **denetlenebilir bir garanti** olmalı.

### Decision
Her entity'ye bir **anchor timestamp** `t*` atanır. Tüm öznitelikler `ft.dfs`'e verilen
**`cutoff_time`** ile üretilir (`features.synthesize()`), bu da yalnızca `t ≤ t*` satırlarını
hesaba dahil eder. Etiket ise yalnızca gelecek penceresinden — `CompiledTask.build_split(anchor)`
(`pql/compile.py`) içindeki SQL'de `(anchor+start, anchor+end]` aralığından, evreni LEFT JOIN edip
`COALESCE(e._val, 0)` ile — hesaplanır. İki pencere asla kesişmez.

Bu, otomatik testle kanıtlanır (`tests/test_leakage.py`):
- anchor sonrası **tüm satırlar silinir** ve öznitelik matrisinin **aynı kaldığı** assert edilir
  (truncation-equality) → öznitelikler gelecekten hiçbir şey okumuyor.
- etiket penceresinin **kesinlikle gelecekte** olduğu ayrıca doğrulanır.

### Consequences
- (+) Sızıntısızlık CI'da kanıtlanır (slogan değil, test).
- (+) `cutoff_time` provenance'ı zaten izlendiğinden, açıklanabilirlik (ADR-006) bedava gelir.
- (−) DFS'i `cutoff_time` ile çağırmak, sınırsız öznitelik üretiminden daha yavaştır — kabul edilen takas.

```bash
.venv\Scripts\python.exe -m pytest tests/ -q          # 25 passed
```

---

<a id="adr-006"></a>
## ADR-006 — Açıklanabilirlik: DFS öznitelik-adı provenance (embedding değil)

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
Düzenleyici uyum (GDPR/KVKK "açıklama hakkı"), güven ve hata ayıklama için her tahminin
**insan-okunur bir "neden"i** olmalı. GNN/foundation-model çıktıları gömme (embedding)
uzayında yaşar; en iyi ihtimalle korelasyonel sütun-katkısı verir — gerçek ilişkisel yol değil.

### Decision
Açıklama, **DFS öznitelik adlarından parse edilen provenance** üzerine kurulur. Bir DFS
öznitelik adı tanımı gereği (tablo + agregasyon + filtre + zaman penceresi) bir join yolu
taşır. `explain.provenance(feature_name)` adı (tablolar, üst-düzey agregasyon)'a ayırır;
`global_importance()` LightGBM gain'i kullanır; `explain_entity()` SHAP varsa onu, yoksa
gain fallback'ini kullanır; `format_card()` entity-bazlı, ASCII-güvenli bir **join-yolu kartı**
basar. Çıktı, *post-hoc tahmin* değil *gerçek hesap yolu*dur.

### Consequences
- (+) Mimari avantaj: baseline (DFS) seçimi açıklamayı bedava verir — Kumo'nun korelasyonel açıklamasından nitelikçe üstün.
- (+) Hem global (model) hem lokal (entity) seviyede; düzenleyici "açıklama hakkı"na uygun.
- (−) Açıklama, DFS öznitelik adlandırma şemasına bağlıdır; primitive seti değişirse parser güncellenmeli.
- (−) SHAP opsiyonel `explain` extra'sındadır; yoksa gain fallback kullanılır (daha kaba ama çalışır).

---

<a id="adr-007"></a>
## ADR-007 — NL→PQL: pluggable LLM (Claude varsayılan) + offline şablon fallback

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
Düz dille soru sormak ("gelecek 30 günde işlem yapmayacak müşteriler") PQL öğrenme bariyerini
sıfırlar — yüksek algılanan değer. Ama tek bir buluta zorunlu LLM bağımlılığı, **local-first**
sözünü (ADR-003) bozar: API yoksa/internet yoksa ürün çalışmaz olur.

### Decision
`nlp.nl_to_pql()` doğal dili PQL'e çevirir ve çıktıyı **tekrar parse ederek doğrular**
(parse hatası LLM'e geri beslenip retry yapılır — self-correction). LLM **pluggable:**
varsayılan Claude (anthropic SDK; model env `RELPATH_LLM_MODEL` veya `claude-sonnet-4-6`).
anthropic kurulu değilse ya da `ANTHROPIC_API_KEY` yoksa, **offline deterministik şablon
eşleyici** devreye girer (churn/forecast/fraud anahtar-kelime yönlendirme; Türkçe+İngilizce).

### Consequences
- (+) NL katmanında bile local-first korunur — offline fallback sayesinde ürün hep çalışır.
- (+) LLM sağlayıcısı değiştirilebilir; tek bir satıcıya kilitlenme yok.
- (−) Offline şablon, serbest-biçimli soruların yalnızca yaygın kalıplarını karşılar (churn/forecast/fraud).
- **Kural:** Claude yolu `ANTHROPIC_API_KEY` ister; yoksa fallback. Varsayılan model `claude-sonnet-4-6`, env ile override edilir.

---

<a id="adr-008"></a>
## ADR-008 — Çekirdek lisansı MIT/BSD/Apache; getML & TabPFN-2.5 karantinada

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
Açık kaynak/self-host konumu (ADR-003) hukuken temiz bir çekirdek gerektirir. İki cazip
bileşen tehlikeli lisans taşır: **getML community = ELv2** (OSI-onaylı değil; SaaS yeniden
satışı yasak) ve **TabPFN-2.5 = ticari kullanım yasak**. Bunlar çekirdeğe girerse self-host
ve ticarileştirme imkânsızlaşır.

### Decision
Çekirdek bağımlılıklar tamamen izinli lisanslı kalır — `pyproject.toml` çekirdeği:
duckdb, pandas, numpy, featuretools (BSD), lightgbm (MIT), scikit-learn, sqlglot (MIT) —
hepsi MIT/BSD/Apache ve **torch'suz.** ELv2/non-commercial bileşenler **çekirdeğe alınmaz;**
yalnızca opsiyonel/karantina eklenti olarak değerlendirilir. (Mevcut `[project.optional-dependencies]`:
`nlp`, `explain`, `tabpfn`, `demo`, `eval`, `dev` — ağır/kısıtlı olanlar izole tutulur;
`eval` extra'sı (`relbench`, `torch`, `torch-frame`) torch'u çekirdekten ayrı tutar.)

### Consequences
- (+) Çekirdek serbestçe self-host ve open-core ticarileştirmeye uygun.
- (+) torch çekirdekte yok → kurulum hafif, CPU-dostu.
- (−) getML'in hızı / TabPFN'in küçük-veri gücü çekirdekte değil — yalnızca opt-in.
- **Kural:** getML (ELv2) ve TabPFN-2.5 (non-commercial) karantinada; asla çekirdek bağımlılığı olmaz.

---

<a id="adr-009"></a>
## ADR-009 — Şema/ilişki modeli için Featuretools EntitySet'i yeniden kullan

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
DFS'i (ADR-002) sızıntı-güvenli çalıştırmak için (ADR-005) tabloları, ilişkileri (PK/FK),
time-index'i ve `cutoff_time`'ı modelleyen bir nesne gerekir. Bunu sıfırdan yazmak,
Featuretools'un zaten olgun biçimde sağladığı `EntitySet` soyutlamasını yeniden icat etmek olurdu.

### Decision
İlişki/şema modeli olarak **Featuretools EntitySet** yeniden kullanılır.
`schema.build_entityset()`, çıkarılan `RelationalSchema`'dan (Column/ForeignKey/Table) bir
EntitySet kurar; `_normalize_dtypes()` DuckDB çıktısını woodwork'ün kabul edeceği
`datetime64[ns]`/`object`'e zorlar. DFS doğrudan bu EntitySet üzerinde çalışır.

### Consequences
- (+) Olgun, test edilmiş ilişki + cutoff modeli; tekerlek yeniden icat edilmez.
- (+) DFS ile sorunsuz entegrasyon (aynı ekosistem).
- (−) woodwork dtype kısıtlarına tabi olunur — pandas pin (ADR-001) ve `_normalize_dtypes()` bu yüzden gerekli.

---

<a id="adr-010"></a>
## ADR-010 — PK/FK/time-index için heuristik çıkarım

**Status:** Accepted · **Tarih:** 2026-06-19

### Context
Gerçek dünyadaki veri dump'ları (CSV, ad-hoc DuckDB dosyaları) çoğu zaman **declared key
taşımaz** — açık PRIMARY KEY / FOREIGN KEY kısıtı yoktur. Ama join inference (ADR-004) ve
sızıntı pencereleri (ADR-005) bir FK grafiği ve time-index'e ihtiyaç duyar.

### Decision
`schema.infer_schema(backend)` anahtarları **heuristik** olarak çıkarır:
- **PRIMARY KEY:** değerleri benzersiz olan bir `*_id`/`id` sütunu; tablonun tekil adıyla
  eşleşen ad tercih edilir.
- **FOREIGN KEY:** adı başka bir tablonun primary key'ine eşit olan, PK olmayan `*_id` sütunu.
- **TIME INDEX:** ilk `TIMESTAMP`/`DATE` sütunu.

`RelationalSchema.join_path(a, b)` yönsüz FK grafiği üzerinde BFS ile çok-hop yolu bulur
(örn. customers ↔ transactions ↔ returns).

### Consequences
- (+) Kısıtsız dump'larda bile "bağlan ve sor" çalışır — manuel şema tanımı gerekmez.
- (+) Çok-hop join'ler otomatik (sample DB'de 2-hop return-risk ~0.689 ROC-AUC bununla mümkün).
- (−) Heuristik yanılabilir (ör. aday anahtar yanlış seçimi); gelecekte açık şema override'ı eklenebilir.

---

## Bir kararı değiştirmek

1. Yeni bir ADR yaz (sıradaki numara), eski ADR'ı **Supersedes** ile referansla.
2. Eski ADR'ın **Status**'ünü `Superseded by ADR-NNN` yap — kaydı silme, tarihçeyi koru.
3. GOLDEN kuralları (ADR-001 pandas pin, ADR-003 local-first, ADR-007 LLM fallback,
   ADR-008 lisans karantinası) değiştirmek **açık onay** ister; bunlar ürün tezini taşır.

> *relpath.dev — açık kaynak, self-hostable, local-first.*
