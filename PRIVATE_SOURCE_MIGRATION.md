# Privat källhämtning

Gotaledens identifierande SQLite-, EQ Timing- och GPX-original lagras i det
privata repot `Stayinhealthyrunning/loppanalys-private-data`. De återställs bara
i en tillfällig Actions-arbetsyta, verifieras mot privat manifest och tas bort
ur arbetsytan innan artefakter publiceras.

Produktionskrav:

- `LOPPANALYS_SOURCE_APP_ID`
- `LOPPANALYS_SOURCE_APP_PRIVATE_KEY`

GitHub-appen ska vara installerad endast på det privata källrepot och ha
`Contents: read`. Saknas en secret, ett källobjekt eller korrekt SHA-256 stoppas
jobbet. Vanlig `GITHUB_TOKEN` används inte för privat källåtkomst.

Lokalt kan en behörig privat checkout användas så här:

```text
python tools/restore_private_sources.py --private-root ../loppanalys-private-data
```

Källfilerna är ignorerade i det publika repot och får inte stageas eller ingå i
PR-diffar, Pages-artefakter, loggar eller Releases.
