PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  base_url TEXT,
  source_type TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS races (
  id INTEGER PRIMARY KEY,
  race_key TEXT NOT NULL UNIQUE,
  section_name TEXT NOT NULL,
  source_race_name TEXT NOT NULL,
  race_type TEXT NOT NULL CHECK(race_type IN ('individual','relay')),
  year INTEGER NOT NULL,
  race_date TEXT,
  nominal_distance_km REAL,
  gpx_distance_km REAL,
  official_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkpoints (
  id INTEGER PRIMARY KEY,
  race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
  checkpoint_key TEXT NOT NULL,
  name TEXT NOT NULL,
  sequence_no INTEGER NOT NULL,
  nominal_distance_km REAL,
  gpx_distance_km REAL,
  is_timing_point INTEGER NOT NULL DEFAULT 1,
  is_relay_exchange INTEGER NOT NULL DEFAULT 0,
  source_station_uid TEXT,
  UNIQUE(race_id, checkpoint_key),
  UNIQUE(race_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS athletes (
  id INTEGER PRIMARY KEY,
  source_external_id TEXT UNIQUE,
  canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  sex TEXT,
  nationality TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teams (
  id INTEGER PRIMARY KEY,
  source_external_id TEXT NOT NULL UNIQUE,
  team_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  class_name TEXT,
  listed_contact_name TEXT,
  member_list_raw TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_members (
  id INTEGER PRIMARY KEY,
  team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  member_name_as_published TEXT NOT NULL,
  source_evidence TEXT,
  raw_json TEXT,
  UNIQUE(team_id, athlete_id)
);

CREATE TABLE IF NOT EXISTS results (
  id INTEGER PRIMARY KEY,
  race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
  source_id INTEGER NOT NULL REFERENCES sources(id),
  source_result_id TEXT NOT NULL,
  entity_type TEXT NOT NULL CHECK(entity_type IN ('athlete','team')),
  athlete_id INTEGER REFERENCES athletes(id),
  team_id INTEGER REFERENCES teams(id),
  bib TEXT,
  name_as_published TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  listed_contact_name TEXT,
  sex TEXT,
  class_name TEXT,
  nationality TEXT,
  club TEXT,
  status TEXT NOT NULL,
  finish_seconds REAL,
  finish_milliseconds INTEGER,
  gross_seconds REAL,
  net_seconds REAL,
  overall_place INTEGER,
  gender_place INTEGER,
  class_place INTEGER,
  start_time TEXT,
  wave_start TEXT,
  passing_time TEXT,
  role_km REAL,
  raw_json TEXT NOT NULL,
  imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(race_id, source_id, source_result_id)
);

CREATE TABLE IF NOT EXISTS splits (
  id INTEGER PRIMARY KEY,
  result_id INTEGER NOT NULL REFERENCES results(id) ON DELETE CASCADE,
  checkpoint_id INTEGER NOT NULL REFERENCES checkpoints(id) ON DELETE CASCADE,
  elapsed_seconds REAL,
  place_overall INTEGER,
  place_gender INTEGER,
  place_class INTEGER,
  source_point_name TEXT,
  split_seconds REAL,
  split_distance_km REAL,
  speed_kmh REAL,
  pace_min_per_km REAL,
  passage_time TEXT,
  is_finish_only_export INTEGER NOT NULL DEFAULT 0,
  raw_json TEXT,
  UNIQUE(result_id, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS relay_leg_assignments (
  id INTEGER PRIMARY KEY,
  result_id INTEGER NOT NULL REFERENCES results(id) ON DELETE CASCADE,
  leg_no INTEGER NOT NULL,
  athlete_id INTEGER REFERENCES athletes(id),
  runner_name_as_published TEXT,
  assignment_status TEXT NOT NULL DEFAULT 'missing'
    CHECK(assignment_status IN ('verified_xml','verified_xml_and_result_list','missing','conflict')),
  source_evidence TEXT,
  source_start_number TEXT,
  raw_json TEXT,
  UNIQUE(result_id, leg_no)
);

CREATE INDEX IF NOT EXISTS idx_results_race ON results(race_id);
CREATE INDEX IF NOT EXISTS idx_results_finish ON results(race_id, finish_seconds);
CREATE INDEX IF NOT EXISTS idx_splits_result ON splits(result_id);
