# Reactome Content Service (snippet given to the Tool Creation Agent)

Checked against https://reactome.org/ContentService on: 2026-11-8

Base URL: https://reactome.org/ContentService

GET /data/mapping/UniProt/{identifier}/pathways?species={taxonomy id or species name}
- identifier: a UniProt accession, for example P04637 (human TP53).
- species: optional filter, for example 9606 for human.
- Header: Accept: application/json
- Returns a JSON list. Each item has `stId` (pathway stable ID) and `displayName` (pathway name).
- Returns HTTP 404 when the identifier has no pathways.