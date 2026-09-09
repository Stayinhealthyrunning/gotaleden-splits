PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY,
  code TEXT NOT NULL,
  provider TEXT NOT NULL,
  source_event_key TEXT NOT NULL,
  name TEXT NOT NULL,
  base_url TEXT,
  source_type TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(provider, source_event_key, code)
);

CREATE TABLE IF NOT EXISTS course_versions (
  course_version TEXT PRIMARY KEY,
  event_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  route_source TEXT NOT NULL,
  elevation_reference_source TEXT,
  whole_course_comparison_group TEXT,
  route_asset TEXT NOT NULL,
  elevation_asset TEXT NOT NULL,
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS races (
  id INTEGER PRIMARY KEY,
  race_key TEXT NOT NULL UNIQUE,
  event_key TEXT NOT NULL,
  race_family TEXT NOT NULL,
  course_version TEXT NOT NULL REFERENCES course_versions(course_version),
  data_status TEXT NOT NULL CHECK(data_status IN ('available','planned')),
  is_analyzable INTEGER NOT NULL DEFAULT 0,
  source_event_key TEXT,
  section_name TEXT NOT NULL,
  source_race_name TEXT,
  race_type TEXT NOT NULL CHECK(race_type IN ('individual','relay')),
  year INTEGER NOT NULL,
  race_date TEXT,
  nominal_distance_km REAL,
  gpx_distance_km REAL,
  route_start_distance_km REAL,
  route_end_distance_km REAL,
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
  route_distance_km REAL,
  is_timing_point INTEGER NOT NULL DEFAULT 1,
  is_relay_exchange INTEGER NOT NULL DEFAULT 0,
  timing_only INTEGER NOT NULL DEFAULT 0,
  analysis_boundary INTEGER NOT NULL DEFAULT 1,
  replay_anchor INTEGER NOT NULL DEFAULT 1,
  speaker_checkpoint INTEGER NOT NULL DEFAULT 0,
  segment_key_to_next TEXT,
  segment_comparison_key_to_next TEXT,
  source_station_uid TEXT,
  UNIQUE(race_id, checkpoint_key),
  UNIQUE(race_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS athletes (
  id INTEGER PRIMARY KEY,
  person_key TEXT NOT NULL UNIQUE,
  identity_status TEXT NOT NULL CHECK(identity_status IN ('verified','local','conflict')),
  identity_scope TEXT NOT NULL CHECK(identity_scope IN ('provider','source_event','race_edition')),
  source_external_id TEXT,
  public_contestant_uid INTEGER,
  canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  sex TEXT,
  nationality TEXT,
  age INTEGER,
  birth_year INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS athlete_external_ids (
  id INTEGER PRIMARY KEY,
  athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  id_type TEXT NOT NULL,
  identity_scope TEXT NOT NULL CHECK(identity_scope IN ('provider','source_event','race_edition')),
  scope_key TEXT NOT NULL,
  external_id TEXT NOT NULL,
  confidence TEXT NOT NULL,
  evidence TEXT,
  identity_namespace TEXT NOT NULL UNIQUE,
  UNIQUE(athlete_id, identity_namespace)
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
  public_contestant_uid INTEGER,
  age INTEGER,
  birth_year INTEGER,
  class_is_ranked INTEGER,
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
  split_place_overall INTEGER,
  split_place_gender INTEGER,
  split_place_class INTEGER,
  source_point_name TEXT,
  source_station_uid TEXT,
  split_seconds REAL,
  split_distance_km REAL,
  source_checkpoint_distance_km REAL,
  speed_kmh REAL,
  pace_min_per_km REAL,
  split_speed_kmh REAL,
  split_pace_min_per_km REAL,
  cumulative_speed_kmh REAL,
  cumulative_pace_min_per_km REAL,
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
