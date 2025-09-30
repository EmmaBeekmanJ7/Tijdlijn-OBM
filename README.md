# OBM-Tijdlijn

Dit project bestaat uit twee hoofdmodules: een **scraper** en een **summarizer**.  
De scraper haalt documenten op en slaat ze op in OpenSearch.  
De summarizer leest deze documenten uit OpenSearch en genereert samenvattingen en een JSON-tijdlijn met relevante informatie.

---

## Structuur

```
resources/
├── MetaDocuments/                # TTL-bestanden voor label-to-URI mapping
├── resource_classes/
│   ├── data_models/
│   │   └── mdto.py               # MDTO en bijbehorende dataclasses
│   ├── repositories/
│   │   └── cl_timeline_os.py     # Opslaan en ophalen van tijdlijnen in OpenSearch
│   └── services/
│       ├── cl_mistral_completions.py  # Wrapper voor Mistral API
│       ├── parser.py             # Document parsing en chunking
│       ├── processor.py          # Document processing pipeline
│       ├── scraper.py            # Ophalen van documenten en metadata
│       ├── timeline.py           # Timeline logica (genereren & samenvatten)
│       ├── summarizer.py         # Samenvattingen per document/tijdlijn
│       └── exceptions.py         # Custom exceptions
├── .env                          # OpenSearch-gegevens en Mistral API key
├── README.md
└── requirements.txt

```

---

## Installatie
1. OpenSearch-account en Mistral account aanmaken

Om dit project te gebruiken, heb je een OpenSearch-cluster nodig. Je kunt een gratis account aanmaken via OpenSearch. Volg de stappen beschreven in deze link: https://opensearch.org/downloads/

Noteer de URL, gebruikersnaam en wachtwoord van je cluster; deze heb je later nodig.

Daarnaast heb je ook een Mistral key nodig. Deze kan je verkrijgen via: https://mistral.ai/


2. Clone de repository:

```bash
git clone https://github.com/EmmaBeekmanJ7/OBM-Tijdlijn.git
cd OBM-Tijdlijn
```

3. Voeg een .env bestand toe met je OpenSearch-gegevens:

```bash
OPENSEARCH_URL=<url>
OPENSEARCH_USERNAME=<username>
OPENSEARCH_PASSWORD=<password>
MISTRAL_API_KEY=<key>
```

## Gebruik

### 1. Build de Docker image

Eenmalig de images bouwen:

```bash
docker compose build
```

### 2. Scraper

Haalt documenten op van Officiële Bekendmakingen en slaat ze op in OpenSearch.

```bash
docker compose run --rm -it scraper
```
### 3. Summarizer

Genereert samenvattingen van documenten en maakt een JSON-tijdlijn.
```bash
docker compose run --rm -it summarizer
```

Optioneel kun je in resources/summarizer.py een specifieke document meegeven om alleen die te updaten.
