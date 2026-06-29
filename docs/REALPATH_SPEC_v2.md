# realpath.dev — Neural Database Predictive Engine

### Strateji, Teknik Mimari ve Go-to-Market Dokümanı — **v2.0**

> **Versiyon:** 2.0.0 · **Tarih:** Haziran 2026
> **Konumlandırma:** *The open-source, self-hostable relational prediction engine.*
> **Bir cümlede:** Veritabanınıza bağlanın, düz İngilizce/Türkçe ile bir tahmin sorun;
> realpath join'leri kendi bulur, sızıntısız öznitelik üretir, modeli eğitir ve **hangi
> ilişkisel yolun kararı verdiğini** açıklayarak yanıtı döndürür — veriyi hiçbir yere
> taşımadan, kendi makinenizde.

![realpath.dev logo](logo.svg)

---

## İçindekiler

0. [Bu v2 Neden Var? (v1'den Farklar)](#0)
1. [Executive Summary & Vizyon](#1)
2. [Pazar ve Rekabet Analizi (Haziran 2026)](#2)
3. [Farklılaştırma / Moat — 4 Sütun](#3)
4. [Sistem Mimarisi (Fazlı ve Dürüst)](#4)
5. [PQL — Predictive Query Language Spesifikasyonu](#5)
6. [Zamansal Sızıntı Güvenliği (Temporal Leakage Safety)](#6)
7. [Açıklanabilirlik (Explainability) Tasarımı](#7)
8. [Değerlendirme: RelBench Benchmark Planı](#8)
9. [Go-to-Market, Yol Haritası ve Riskler](#9)
- [Ek A: Kaynakça](#ekA)
- [Ek B: Sözlük](#ekB)

---

<a id="0"></a>
## 0. Bu v2 Neden Var? (v1'den Farklar)

İlk doküman (`v1.0.0-PROD`) iddialı bir **vizyon ve pitch** metniydi: kurumsal mimari
diyagramları, AWS EKS GPU manifestleri, Snowflake SPCS dağıtımı, GNN + Relational
Transformer mimarisi ve RelBench benchmark tabloları içeriyordu. Ancak v1'in iki temel
sorunu vardı:

1. **Çalışan kod yoktu** — tamamı slayt seviyesinde bir vaatti.
2. **Kategori lideri Kumo.AI'nin bir klonuydu.** Aynı kavram (Relational Foundation Model),
   aynı arayüz (PQL), aynı dağıtım (Snowflake/Databricks), aynı benchmark (RelBench).
   Kapalı, iyi finanse edilmiş ve hızlı bir oyuncuyla **onun kendi sahasında**, onun
   silahlarıyla rekabet etmek kaybedilen bir savaştır.

**v2'nin tezi:** Kumo'yu taklit etme — **Kumo'nun yapısal olarak yapamadığını yap.**

| | v1 (pitch) | **v2 (bu doküman)** |
|---|---|---|
| Doğa | Vizyon dokümanı | Strateji **+ çalışan prototip** |
| Konum | Kumo klonu | Kumo'nun **karşıtı** (açık kaynak, self-host, local-first) |
| Mimari | "Önce GNN" (en pahalı yol) | **Önce ucuz baseline** (DFS+GBDT), GNN sonra |
| Dağıtım | Snowflake/Databricks-kilitli | **DuckDB local-first**, warehouse opsiyonel |
| Açıklanabilirlik | Belirtilmemiş | **Birinci sınıf özellik** (join-yolu provenance) |
| Kanıt | Alıntılanan tablolar | **Kendi çalıştırdığımız RelBench eval'i** |

Bu değişikliklerin gerekçesi, aşağıdaki gerçek piyasa ve akademik araştırmaya dayanır.

---

<a id="1"></a>
## 1. Executive Summary & Vizyon

### 1.1 Problem: "Öznitelik Mühendisliği Cehennemi"

Dünyanın en değerli verisi (finansal işlemler, müşteri yolculukları, tedarik zinciri,
klinik kayıtlar) **ilişkisel** olarak yaşar — onlarca tabloya yayılmış, primary/foreign key
ile bağlanmış. Ama egemen ML araçları (XGBoost, LightGBM, CatBoost) yalnızca **tek bir düz
tablo** görebilir.[^rdl][^kumo] Aradaki boşluğu veri bilimciler kapatır: aylar süren elle
SQL `JOIN` + `GROUP BY` yazarak "öznitelik boru hatları" kurmak. Bu süreç pahalı, yavaş,
hataya açık ve her yeni tahmin sorusunda sıfırdan tekrarlanır.

### 1.2 Paradigma: İlişkisel Derin Öğrenme (Relational Deep Learning, RDL)

RDL, veritabanını **zamansal heterojen bir grafik** olarak modeller: her tablonun her
satırı bir düğüm, her PK–FK bağlantısı bir kenar, her satırın görünür olduğu an bir zaman
damgası.[^rdl] Böylece "öznitelik mühendisliği" otomatikleşir — model, ilişkisel topolojiyi
tarayarak hangi sinyalin önemli olduğunu kendisi keşfeder. Bu fikrin akademik temeli
Stanford'da (Fey, Leskovec ve ark., ICML'24) atıldı; ticari öncüsü **Kumo.AI**.[^rdl][^kumo]

### 1.3 realpath.dev'in Vizyonu

> **"Relational Deep Learning'i demokratikleştirmek."**

Kumo bu teknolojiyi kurumsal, kapalı ve bulut-kilitli bir SaaS olarak sunuyor. realpath.dev
aynı değeri **açık kaynak, self-hostable ve local-first** olarak sunar. Bir veri bilimci
veya geliştirici, kendi dizüstü bilgisayarında, verisini hiçbir yere taşımadan, üç satır
kodla (ya da bir cümle düz dille) ilişkisel tahmin alabilmeli.

**Dürüst kapsam notu:** realpath.dev bir "foundation model" (KumoRFM gibi sıfır-eğitim
in-context model) **değildir** — en azından bugün değil. v2 prototipi, bilinçli olarak
**görev-başına hızlı eğitilen güçlü bir baseline** (Deep Feature Synthesis + Gradient
Boosting) üzerine kuruludur. Bu, basit görünebilir; ama §2.4 ve §8'de göstereceğimiz gibi,
**bu baseline birçok gerçek görevde GNN/RDL ile yarışır veya onu geçer** — kat kat daha
ucuza. Foundation-model yolu (§4, Faz 3) yol haritasındadır, vitrin değildir.

---

<a id="2"></a>
## 2. Pazar ve Rekabet Analizi (Haziran 2026)

### 2.1 Kategori Lideri: Kumo.AI / KumoRFM-2

Kumo.AI (Jure Leskovec ve ekibi), **KumoRFM** ile kategoriyi tanımladı: çok tablolu
veritabanı üzerinde, **görev-başına eğitim olmadan** (in-context learning) tahmin yapan bir
**Relational Foundation Model**.[^kumo][^rfm2] 2025–2026'da **KumoRFM-2** ile güncellendi.

**Güçlü yanları:**
- **In-context learning:** Çıkarım anında geçmiş satırlardan otomatik etiketli alt-grafikler
  örnekleyerek "context example" üretir — LLM'lerdeki few-shot mantığı.[^rfm2]
- **Hız & ölçek:** ~1 sn çıkarım; "Online Serving" ile sub-100ms / binlerce QPS;
  memory-mapped grafik motoru 500B+ satır.[^kumo-online]
- **Warehouse-native:** Snowflake & Databricks içinde, veri dışarı çıkmadan çalışır.[^kumo]
- **Agent-native:** MCP server + Python SDK.[^kumo-mcp]

**Yapısal zayıflıkları (bizim açtığımız kapılar):**
| Zayıflık | Açıklama | realpath fırsatı |
|---|---|---|
| **Kapalı kaynak** | Model ağırlıkları/kodu kapalı, satış-odaklı | Açık kaynak çekirdek |
| **Şeffaf olmayan fiyat** | Genel fiyat sayfası yok; enterprise = "contact sales" | Self-host = ücretsiz; küçük-veri bedava |
| **Bulut kilidi** | Snowflake/Databricks ekosistemine bağlı | **DuckDB local-first**, warehouse opsiyonel |
| **On-prem/air-gapped yok** | Düzenlemeli sektörler (sağlık, kamu, finans) dışarıda | Tamamen offline çalışır |
| **Korelasyonel açıklama** | "Hangi sütun katkı yaptı" var ama nedensel/denetlenebilir değil | **Join-yolu provenance** |
| **Yalnızca yapısal veri** | Metin/belge muhakemesi yok | (yol haritası) LLM + ilişkisel füzyon |

### 2.2 Bitişik / Dolaylı Rakipler

- **getML** — ilişkisel/zaman-serisi öznitelik mühendisliği (FastProp/Multirel); Featuretools'tan
  60–1000× hızlı.[^getml] Ama *foundation model değil*, klasik ML için öznitelik üretir;
  community sürümü **ELv2** (OSI-onaylı açık kaynak **değil**, SaaS yeniden-satışı yasak).
- **Featuretools / Deep Feature Synthesis (Alteryx)** — olgun, ücretsiz (BSD), çok-tablolu
  otomatik agregasyon; ama *düzleştirir* (tek-satır-per-entity), sıfır-shot yok, model
  eğitmeyi size bırakır.[^ft]
- **Snowflake Cortex ML Functions** — SQL içi forecasting/classification/anomaly; kolay ama
  **tek-tablo / zaman-serisi** odaklı, çok-tablolu grafik öğrenme değil.[^cortex]
- **Databricks Mosaic AI / AutoML** — güçlü ama DIY MLOps; push-button ilişkisel tahmin değil.
- **RelationalAI** — Snowflake Native App "Knowledge Graph Coprocessor"; akıl yürütme/kural
  odaklı, tahmin ikincil ve **yalnızca Snowflake**.[^relai]
- **Continual.ai** — "warehouse üzerinde deklaratif ML" oyuncusuydu; ekip Snowflake'e geçti,
  ürün etkin biçimde kapandı — bıraktığı boşluğu bugün Kumo dolduruyor.

### 2.3 Pazar Haritası — Tek Bakışta

```
                 Açık Kaynak / Self-host
                          ▲
        Featuretools •    │    • realpath.dev  ◀── BOŞ KÖŞE (hedefimiz)
            getML •       │
   ───────────────────────┼───────────────────────▶  Push-button
   Manuel öznitelik       │              Otomatik ilişkisel tahmin
                          │    • Kumo / KumoRFM
        Snowflake Cortex •│    • RelationalAI
            Databricks •  │
                          ▼
                  Kapalı / Bulut-kilitli
```

Sağ-üst köşe — **otomatik ilişkisel tahmin + açık kaynak/self-host** — bugün **boş**.
realpath.dev'in tüm stratejisi bu köşeyi sahiplenmektir.

### 2.4 Kritik Bulgu: "GNN Şart Değil" (80/20)

En önemli stratejik veri: **getml-relbench** karşılaştırması, propositionalization +
gradient boosting'in birçok RelBench görevinde GNN/RDL'i **eşitlediğini veya geçtiğini**
gösteriyor — çok daha ucuza:[^getml-rb]

| Görev | DFS/FastProp + GBDT | RDL/GNN |
|---|---|---|
| rel-amazon item-churn | **0.831** | 0.828 |
| rel-hm user-churn | **0.703** | 0.699 |
| rel-hm item-sales (MAE, düşük=iyi) | **0.031** | 0.056 |

**Sonuç:** GNN'in net üstünlüğü esas olarak **link-prediction / öneri** ve derin çok-hop
zamansal sinyal gerektiren görevlerde. Tablo-düzeyi sınıflandırma/regresyon görevlerinin
çoğunda ucuz baseline yeterli. Bu, prototip kararımızı (önce baseline) doğrudan haklı çıkarır
ve "RDL = mutlaka pahalı GPU" mitini kırar — bu da açık kaynak/local-first konumumuzun
teknik temelidir.

---

<a id="3"></a>
## 3. Farklılaştırma / Moat — 4 Sütun

Her sütun, "**Kumo bunu neden kolayca yapamaz?**" sorusuyla gerekçelendirilmiştir.

### Sütun 1 — Açık Kaynak + Self-Host + Local-First (DuckDB)
- **Ne:** Çekirdek motor MIT/BSD lisanslı; tek `pip install`; **DuckDB** ile dizüstünde,
  veri hiç dışarı çıkmadan çalışır. İnternet, warehouse, hesap gerektirmez.
- **Neden Kumo yapamaz:** İş modeli kapalı SaaS + warehouse ortaklıklarına dayanır.
  Açık kaynak yapmak gelir modelini ve bulut kilidini imha eder. Bu yapısal bir kilit.
- **Kime hitap eder:** Düzenlemeli sektörler (sağlık/kamu/finans), KOBİ'ler, startup'lar,
  hava-boşluklu (air-gapped) ortamlar, "veri çıkamaz" politikası olan herkes.

### Sütun 2 — Doğal Dil → PQL (LLM arayüzü)
- **Ne:** Kullanıcı "*gelecek 30 günde alışveriş yapmayacak müşterileri bul*" yazar; sistem
  şema-farkında bir LLM ile bunu geçerli **PQL**'e çevirir, SQLGlot ile **doğrular**, sonra
  çalıştırır. Yanlış/uydurma sorgu üretimi parser ile yakalanır.
- **Neden moat:** Düşük efor, yüksek algılanan değer. PQL'i öğrenme bariyerini sıfırlar;
  "veritabanıyla konuşma" deneyimi sunar. LLM sağlayıcısı pluggable (Claude varsayılan;
  local LLM / offline şablon fallback).

### Sütun 3 — Açıklanabilirlik (Join-Yolu Provenance)
- **Ne:** Her tahmin için "**bu kararı hangi tablolar, hangi agregasyonlar, hangi join
  yolu** verdi" gösterilir. DFS öznitelikleri doğası gereği yorumlanabilir
  (`SUM(transactions.amount WHERE ...)` gibi); bunları LightGBM gain/SHAP ile birleştirip
  hem global hem entity-bazlı açıklama üretiriz.
- **Neden Kumo yapamaz (kolayca):** GNN/foundation-model gömme uzayında çalışır; çıktısı
  korelasyonel sütun-katkısıdır, **insan-okunur ilişkisel yol** değil. Bizim baseline'ımız
  bu açıklamayı *bedavaya* verir — mimari avantaj.
- **Neden önemli:** Düzenleyici uyum (GDPR/KVKK "açıklama hakkı"), güven, hata ayıklama.

### Sütun 4 — Dikey Şablonlar (Vertical Templates)
- **Ne:** Yatay sorgu diline ek olarak, hazır paketlenmiş çözümler: `churn`, `fraud`,
  `forecast`. Her biri parametrik bir PQL + makul varsayılanlar + alana özgü açıklama.
  `realpath.churn(entity="customers", horizon="30 days")` → bitti.
- **Neden moat:** Kumo yatay bir platform satar; alıcı yine de problemi modellemeli.
  Şablonlar "time-to-value"yu dakikalara indirir ve dikey pazarlama (SEO, içerik) sağlar.

---

<a id="4"></a>
## 4. Sistem Mimarisi (Fazlı ve Dürüst)

### 4.1 Üç Faz

```
Faz 1 (PROTOTİP — bu sürüm)      Faz 2 (BÜYÜME)            Faz 3 (VİZYON)
─────────────────────────       ───────────────           ──────────────
DFS + GradientBoosting          + RDL/GNN backend         + Relational
(local-first, CPU)                (relbench + PyG)           Foundation Model
                                                            (in-context, zero-train)
NL→PQL · Explain · Templates    + Warehouse konnektörleri  + Streaming / real-time
DuckDB / Postgres                 (Snowflake/Databricks)     + Multimodal (metin)
```

**Strateji:** Değerin %80'ini Faz 1'de, maliyetin %20'siyle teslim et (§2.4). GNN ve
foundation-model, kanıtlanmış talep ve gelir geldikçe eklenir — vitrin değil, yol haritası.

### 4.2 Faz 1 Veri Akışı (Prototip)

```
┌──────────────┐   ┌───────────────┐   ┌──────────────────┐   ┌─────────────┐
│  CONNECT     │──▶│  SCHEMA        │──▶│  PQL COMPILE     │──▶│  TASK BUILD │
│ DuckDB/PG    │   │ FK-grafiği +   │   │ NL→PQL (LLM)     │   │ entity @    │
│ tabloları    │   │ EntitySet      │   │ → AST → join     │   │ anchor ts + │
│              │   │ (Featuretools) │   │   inference      │   │ label       │
└──────────────┘   └───────────────┘   └──────────────────┘   └──────┬──────┘
                                                                      │
        ┌─────────────────────────────────────────────────────────────┘
        ▼
┌──────────────────┐   ┌──────────────────┐   ┌─────────────────────────┐
│  FEATURES (DFS)  │──▶│  MODEL           │──▶│  EXPLAIN + SERVE        │
│ cutoff_time ile  │   │ LightGBM (auto   │   │ join-yolu provenance,   │
│ sızıntı-güvenli  │   │ clf/reg) /TabPFN │   │ tahmin tablosu, SDK/CLI │
└──────────────────┘   └──────────────────┘   └─────────────────────────┘
```

### 4.3 "Zero-Data-Movement" — Bizim Yorumumuz

v1 bunu "warehouse içinde çalış" diye tanımlıyordu (Snowflake SPCS). Biz daha radikal
yorumluyoruz: **veri zaten makinenizde** (DuckDB dosyası) ya da kendi sunucunuzda (Postgres);
realpath onun *yanında* çalışır. Hiçbir SaaS'a, hiçbir buluta veri gitmez. Warehouse'a bağlanmak
(Faz 2) bir *opsiyon*'dur, *zorunluluk* değil — Kumo'nun aksine.

### 4.4 Teknoloji Yığını ve Lisanslar

| Katman | Bileşen | Lisans | Rol |
|---|---|---|---|
| Depolama | **DuckDB** | MIT | Local-first analitik motor |
| Şema | **Featuretools EntitySet** | BSD-3 | Entity + ilişki + cutoff modeli |
| Derleyici | **SQLGlot** | MIT | PQL parse/validate/transpile |
| Öznitelik | **Featuretools DFS** | BSD-3 | Sızıntı-güvenli propositionalization |
| Model | **LightGBM** | MIT | Gradient boosting (clf/reg) |
| Model (küçük veri) | **TabPFN** | Apache+attr. | Tabular FM (opsiyonel) |
| NL→PQL | **Claude (anthropic SDK)** | API | Doğal dil arayüzü (pluggable) |
| Açıklama | **SHAP / LGBM gain** | MIT | Öznitelik katkısı |
| Eval | **relbench** | MIT | Benchmark + metrik (opsiyonel extra) |

**Lisans disiplini:** Çekirdek tamamen izinli (MIT/BSD/Apache). getML (ELv2) ve
TabPFN-2.5 (ticari kullanım yasak) **çekirdeğe alınmaz** — yalnızca opsiyonel/karantina
eklenti olarak sunulur.

---

<a id="5"></a>
## 5. PQL — Predictive Query Language Spesifikasyonu

PQL, "ne tahmin etmek istediğinizi" deklaratif olarak söyleten bir DSL'dir; "nasıl"ı
derleyici halleder. v1'in gramerini **koruyoruz** (geriye uyum), netleştirerek.

### 5.1 Gramer

```
PREDICT  <target_expr>
FOR EACH <Entity_Table.Primary_Key>
[ WHERE  <filters> ]
[ ASSUMING <segment_filters> ]      -- (v2 eklentisi: tahmin evrenini daraltır)
```

`target_expr`, bir **zaman-pencereli agregasyon**'dur:
```
AGG( <Table.Column | Table.*> , <start_offset> , <end_offset> , <unit> ) [ <op> <value> ]
AGG ∈ { COUNT, SUM, AVG, MIN, MAX, FIRST, LAST, LIST_DISTINCT }
unit ∈ { days, weeks, months }
op   ∈ { ==, !=, >, >=, <, <= }    -- varsa → sınıflandırma, yoksa → regresyon
```

### 5.2 Örnekler

**Müşteri churn'ü (ikili sınıflandırma):** "Gelecek 30 günde hiç işlem yapmayacak müşteriler"
```sql
PREDICT  COUNT(TRANSACTIONS.*, 0, 30, days) == 0
FOR EACH CUSTOMERS.CUSTOMER_ID
```

**Talep tahmini (regresyon):** "Her ürün için gelecek 3 ayın toplam satışı"
```sql
PREDICT  SUM(TRANSACTIONS.QUANTITY, 0, 3, months)
FOR EACH ARTICLES.ARTICLE_ID
```

**Fraud (segmentli sınıflandırma):** "Yüksek-tutarlı işlemlerden hangileri geri-çekilecek (chargeback)"
```sql
PREDICT  COUNT(CHARGEBACKS.*, 0, 60, days) > 0
FOR EACH TRANSACTIONS.TX_ID
ASSUMING TRANSACTIONS.AMOUNT > 1000
```

### 5.3 Derleyici Aşamaları

1. **Lexing/Parsing (AST):** SQLGlot tabanlı tokenizer + PQL grameri → soyut sözdizim ağacı.
2. **Join Inference:** FK-grafiğinde `Entity_Table` ↔ hedef/öznitelik tabloları arası en kısa
   join yolları otomatik bulunur — elle `JOIN` yazmaya gerek yok. (v1'deki "Join Inferral".)
3. **Temporal Decomposition:** İki pencere kesin izole edilir →
   *Label window* `[anchor, anchor+horizon]` (geleceğe bakar, **yalnızca etiket için**) ve
   *Feature window* `(-∞, anchor]` (geçmişe bakar, **yalnızca girdi için**). Ayrıntı §6.
4. **Task Lowering:** Her entity için (anchor timestamp, label) çiftleri üretilir; çıktı,
   Featuretools'a verilecek `cutoff_time` tablosu + hedef vektörüdür.

### 5.4 NL→PQL

Düz dil → şema-farkında LLM prompt → PQL string → **tekrar parse ederek doğrulama**. Parse
başarısızsa LLM'e hata geri beslenir (self-correction, max N tur). API yoksa **deterministik
şablon fallback** (örüntü eşleme ile yaygın churn/forecast sorularını karşılar). Bu sayede
"local-first" sözü NL katmanında da bozulmaz.

---

<a id="6"></a>
## 6. Zamansal Sızıntı Güvenliği (Temporal Leakage Safety)

**Problem.** İlişkisel tahmolinde en sinsi hata, modelin *gelecekteki* veriyi görerek
eğitilmesidir (label leakage). Akademi bunu RDL'in **çözülmemiş açık problemlerinden** sayar;
çoğu sistem bunu ad-hoc halleder.[^survey][^leak] v1 bunu "Anchor Timestamp" diye anıyordu
ama mekanizma soyuttu.

**realpath'in çözümü — yapısal garanti.** Her entity'ye bir **anchor timestamp** `t*` atanır.
Tüm öznitelikler Featuretools `cutoff_time` ile üretilir; bu, motorun **yalnızca `t ≤ t*`
olan satırları** öznitelik hesabına dahil etmesini *garanti* eder. Etiket ise yalnızca
`(t*, t*+horizon]` penceresinden hesaplanır. İki pencere asla kesişmez:

```
   geçmiş (öznitelikler)            gelecek (etiket)
 ◀───────────────────────●───────────────────────▶
        t ≤ t*          t*        t* < t ≤ t*+H
   FEATURE WINDOW      anchor       LABEL WINDOW
```

**Denetlenebilirlik.** Bunu bir slogan değil, **otomatik test** yapıyoruz: `tests/` içinde,
üretilen her özniteliğin provenance'ını izleyip `t*` sonrası hiçbir kaynak satıra
dokunmadığını doğrulayan bir sızıntı-denetçisi var (§8.2). "Sızıntı yok" iddiası CI'da kanıtlanır.

Bu, §3'teki açıklanabilirlik sütununu da besler: provenance zaten izlendiği için, "neden"i
göstermek bedavaya gelir.

---

<a id="7"></a>
## 7. Açıklanabilirlik (Explainability) Tasarımı

**Hedef:** Her tahmin için insan-okunur "**neden**". İki seviye:

1. **Global (model seviyesi):** Hangi join-yolları/agregasyonlar genelde en belirleyici?
   LightGBM gain importance, DFS öznitelik tanımına geri eşlenir. Örn:
   *"`MEAN(transactions.amount, last 90d)` ve `COUNT(returns.*, last 30d)` churn'ün en güçlü
   2 sürücüsü."*

2. **Lokal (entity seviyesi):** Bu *tek* müşteri neden riskli? SHAP değerleri + öznitelik
   provenance → "**join yolu kartı**":
   ```
   customer #4471 — churn olasılığı 0.87  (▲ yüksek)
   ├─ transactions → MEAN(amount, 90d) = 12₺      katkı: +0.41  (düşük harcama)
   ├─ transactions → COUNT(*, 30d)     = 0         katkı: +0.28  (son 30g hareketsiz)
   └─ returns      → COUNT(*, 60d)     = 3         katkı: +0.12  (çok iade)
   ```

**Neden mimari avantaj:** DFS öznitelikleri *tanımları gereği* ilişkisel yol taşır
(tablo + agregasyon + filtre + zaman penceresi). GNN gömmelerinin aksine bu açıklama
*post-hoc tahmin* değil, *gerçek hesap yolu*dur. Kumo'nun korelasyonel sütun-katkısından
niteliksel olarak üstündür ve düzenleyici "açıklama hakkı" için uygundur.

---

<a id="8"></a>
## 8. Değerlendirme: RelBench Benchmark Planı

İddiaları kanıtla — alıntılama, **kendin çalıştır.**

### 8.1 Datasetler ve Görevler

Stanford **RelBench v2** (11 DB / 66 görev) üzerinde, başlangıçta 2 temsili görev:[^relbench][^relbench2]
- **Sınıflandırma:** `rel-hm` *user-churn* (veya `rel-amazon` *user-churn*) → metrik **ROC-AUC**.
- **Regresyon:** `rel-hm` *item-sales* → metrik **MAE**.

### 8.2 Karşılaştırma ve Hedefler

| Karşılaştırma | Amaç |
|---|---|
| realpath (DFS+LGBM) **vs** LightGBM-no-features | Öznitelik üretiminin değerini kanıtla |
| realpath **vs** yayınlanan RDL/GNN baseline | "Ucuz baseline yarışıyor" tezini doğrula (§2.4) |
| **Sızıntı testi** | Hiçbir özniteliğin anchor sonrası veri kullanmadığını CI'da kanıtla |
| **PQL parser birim testleri** | Gramerin doğruluğu |

**Tek komut:** `python -m realpath.eval --dataset rel-hm --task user-churn` → skor + baseline
farkı yazdırır. (relbench, `realpath[eval]` opsiyonel extra'sında izole; çekirdek torch'suz.)

---

<a id="9"></a>
## 9. Go-to-Market, Yol Haritası ve Riskler

### 9.1 GTM — Açık Kaynak Öncelikli

1. **GitHub-first launch:** MIT çekirdek + tek-komut demo + RelBench eval. "Show HN /
   r/MachineLearning" için doğal hikâye: *"Kumo'nun açık kaynak alternatifi, dizüstünüzde."*
2. **NL→PQL interaktif demo:** Web sitesinde kullanıcı kendi şemasını yükler, düz dille sorar,
   PQL + Python SDK kodu üretir. Yüksek-kaliteli geliştirici lead'i toplar. (v1'deki bu fikir
   *iyiydi* — koruyoruz.)
3. **Dikey içerik/SEO:** "Open-source churn prediction", "self-hosted demand forecasting",
   "relational deep learning without GPUs" gibi long-tail kümeleri.
4. **OSS → ticari köprü:** Çekirdek bedava; gelir Faz 2'de **managed/warehouse konnektörleri,
   ekip özellikleri, destek** ile (open-core modeli).

### 9.2 Yol Haritası

| Çeyrek | Kilometre taşı |
|---|---|
| **Şimdi** | Faz 1 prototip: connect→PQL→DFS→LGBM→explain; NL→PQL; 3 şablon; RelBench eval |
| +1 | Postgres/MySQL konnektörleri; Streamlit Cloud demo; PyPI yayını |
| +2 | RDL/GNN backend (relbench+PyG) opsiyonel; link-prediction/öneri görevleri |
| +3 | Warehouse konnektörleri (Snowflake/Databricks read); managed sürüm |
| Vizyon | Relational Foundation Model (in-context); streaming; multimodal |

### 9.3 Riskler ve Azaltım

| Risk | Azaltım |
|---|---|
| Kumo'nun hızı/fonu | Onun sahasında değil, **açık kaynak/local-first** sahasında oyna |
| GNN olgunluğu/maliyeti | Faz 1 GNN'siz değer üretir; GNN talebe bağlı |
| Açık kaynak gelir modeli | Open-core: çekirdek bedava, warehouse/managed ücretli |
| LLM bağımlılığı (NL→PQL) | Pluggable + offline şablon fallback |
| Lisans tuzakları (getML/TabPFN-2.5) | Çekirdek izinli; riskli bileşenler karantinada |

---

<a id="ekA"></a>
## Ek A: Kaynakça

[^rdl]: Fey, Hu, Huang, Robinson, Ying, You, Leskovec. *Position: Relational Deep Learning*, ICML 2024. https://proceedings.mlr.press/v235/fey24a.html
[^kumo]: Kumo.AI — KumoRFM tanıtımı. https://kumo.ai/company/news/kumo-relational-foundation-model/
[^rfm2]: KumoRFM-2 teknik raporu. https://arxiv.org/html/2604.12596v1 · Duyuru: https://kumo.ai/company/news/kumorfm-2-the-most-powerful-predictive-model-for-humans-and-agents/
[^kumo-online]: Kumo Online Serving (sub-100ms). https://kumo.ai/company/news/low-latency-high-throughput-predictions-with-kumorfm-2-fine-tuning/
[^kumo-mcp]: KumoRFM MCP server. https://kumo.ai/company/news/kumorfm-mcp/
[^getml]: getML community. https://github.com/getml/getml-community
[^getml-rb]: getml-relbench karşılaştırması. https://github.com/getml/getml-relbench
[^ft]: Featuretools / Deep Feature Synthesis. https://github.com/alteryx/featuretools
[^cortex]: Snowflake Cortex ML Functions. https://docs.snowflake.com/en/guides-overview-ml-functions
[^relai]: RelationalAI Snowflake Native App GA. https://www.relational.ai/post/relationalai-knowledge-graph-coprocessor-is-generally-available-as-a-snowflake-native-app
[^relbench]: RelBench (Stanford SNAP). https://github.com/snap-stanford/relbench · NeurIPS'24: https://arxiv.org/abs/2407.20060
[^relbench2]: RelBench v2. https://arxiv.org/pdf/2602.12606
[^survey]: *Relational Deep Learning: Challenges, Foundations and Next-Generation Architectures*, KDD'25. https://arxiv.org/html/2506.16654v1
[^leak]: RelGNN (atomic routes), ICML'25. https://arxiv.org/abs/2502.06784 · RelGT, ICLR'26. https://arxiv.org/abs/2505.10960 · Griffin. https://arxiv.org/abs/2505.05568

<a id="ekB"></a>
## Ek B: Sözlük

- **RDL (Relational Deep Learning):** Veritabanını zamansal heterojen grafik olarak görüp
  uçtan uca derin öğrenme uygulama paradigması.
- **RFM (Relational Foundation Model):** Görev-başına eğitim olmadan, in-context tahmin yapan
  önceden-eğitilmiş ilişkisel model (örn. KumoRFM).
- **PQL (Predictive Query Language):** "Ne tahmin edileceğini" deklaratif söyleyen DSL.
- **DFS (Deep Feature Synthesis):** İlişkili tablolarda otomatik agregasyonla öznitelik üretimi.
- **Propositionalization:** Çok-tablolu ilişkisel veriyi tek düz öznitelik tablosuna indirgeme.
- **Anchor timestamp / cutoff time:** Bir entity için "şimdi" anı; öznitelikler bundan
  öncesini, etiket sonrasını görür → sızıntı engellenir.
- **Local-first:** Verinin ve hesabın kullanıcı makinesinde kalması; buluta bağımlı olmama.

---

> *realpath.dev — "tablolardan grafik patikalarına ve sinirsel tahminlere giden ilişkisel yol."*
> Açık kaynak. Self-hostable. Local-first.
