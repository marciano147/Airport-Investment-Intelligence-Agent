# Data Cache

This folder contains review-stable public data used by the compute layer.

- `airports.csv`: US scheduled-service airport metadata from OurAirports.
- `runways.csv`: runway counts and longest-runway metadata derived from OurAirports.
- `enplanements.csv`: cleaned FAA 2024 commercial-service passenger boardings.
- `congestion_baselines.csv`: labeled prototype structural congestion scores used when FAA NAS has no active program.
- `long_haul_proxies.csv`: labeled prototype long-haul / international share proxies.

`data/chat_history.db` is created locally by the Streamlit app and is ignored by git.
