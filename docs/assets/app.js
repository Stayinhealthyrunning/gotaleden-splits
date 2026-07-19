let DATA;
let ROUTE;
let currentRace = "individual-75-2026";

const fmtTime = seconds => {
  if (seconds == null) return "–";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}:${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}`;
};

function render() {
  const race = DATA.races[currentRace];
  const records = race.records;
  const query = document.querySelector("#search").value.trim().toLowerCase();
  const filtered = records.filter(r => {
    const text = `${r.name || ""} ${r.bib || ""} ${r.class_name || ""}`.toLowerCase();
    return !query || text.includes(query);
  });

  document.querySelector("#race-title").textContent = race.section;
  document.querySelector("#record-count").textContent = records.length.toLocaleString("sv-SE");
  document.querySelector("#finished-count").textContent = records.filter(r => r.status === "FINISHED").length.toLocaleString("sv-SE");
  document.querySelector("#gpx-distance").textContent = `${race.gpx_distance_km.toFixed(1)} km`;

  const body = document.querySelector("#results-body");
  body.innerHTML = filtered
    .sort((a,b) => (a.overall_place ?? 999999) - (b.overall_place ?? 999999))
    .slice(0, 40)
    .map(r => `<tr>
      <td>${r.overall_place ?? "–"}</td>
      <td><strong>${r.name}</strong>${r.bib ? `<br><small>#${r.bib}</small>` : ""}</td>
      <td>${r.class_name || "–"}</td>
      <td>${r.finish_time_formatted || fmtTime(r.finish_seconds)}</td>
      <td>${r.status}</td>
    </tr>`).join("");

  document.querySelectorAll(".race-switcher button").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.race === currentRace);
  });
}

Promise.all([
  fetch("data/results-2026.json").then(r => r.json()),
  fetch("data/route.json").then(r => r.json())
]).then(([data, route]) => {
  DATA = data;
  ROUTE = route;
  document.querySelector("#full-route-distance").textContent = `${route.full_distance_km.toFixed(1)} km`;
  document.querySelector("#short-route-distance").textContent = `${route.floda_start.remaining_distance_km.toFixed(1)} km`;
  render();
});

document.querySelectorAll(".race-switcher button").forEach(btn => {
  btn.addEventListener("click", () => {
    currentRace = btn.dataset.race;
    render();
  });
});
document.querySelector("#search").addEventListener("input", render);
