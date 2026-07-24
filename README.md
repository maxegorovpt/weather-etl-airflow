weather-etl-airflow/
├── dags/
│   └── weather_etl_dag.py
├── plugins/
│   └── weather/
│       ├── extract.py
│       ├── transform.py
│       └── load.py
├── sql/
│   ├── create_tables.sql
│   └── upsert.sql
├── dashboard/
│   └── app.py          # if using Streamlit
├── tests/
│   └── test_transform.py
├── docker-compose.yaml
├── .env                # API keys, DB creds (gitignored)
├── requirements.txt
└── README.md