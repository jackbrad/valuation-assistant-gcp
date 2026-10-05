from google.cloud import bigquery
from config.loader import settings

client = bigquery.Client(project=settings["project"]["project_id"])
query = """
SELECT doc_id, page, section, text
FROM `takehome-gcp.val_raw.text_blocks`
WHERE doc_id = 'DOC-INS-000014' AND page = 2 AND text LIKE '%Addition%'
"""
rows = list(client.query(query).result())
print(f"Total matching BigQuery rows: {len(rows)}")
for r in rows:
    print("--------------------------------------------------")
    print(f"DOC ID:  {r['doc_id']}")
    print(f"PAGE:    {r['page']}")
    print(f"SECTION: {r['section']}")
    print(f"TEXT:    {r['text']}")
