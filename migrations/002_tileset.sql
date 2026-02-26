CREATE TABLE IF NOT EXISTS tileset (
  tile_job_id  UUID REFERENCES tile_job(tile_job_id) ON DELETE CASCADE,
  ifc_class    TEXT NOT NULL,
  tileset_url  TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'PENDING',
  error        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tile_job_id, ifc_class)
);

CREATE INDEX IF NOT EXISTS idx_tileset_job
  ON tileset(tile_job_id);
