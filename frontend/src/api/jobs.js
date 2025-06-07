const API = import.meta.env.VITE_API_URL || "http://localhost:58000";

export async function fetchJobs() {
  const res = await fetch(`${API}/jobs`);
  return res.json();
}

export async function createJob(data) {
  const res = await fetch(`${API}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}
