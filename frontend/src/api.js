/** Thin wrapper over fetch. Every call goes to /api on our own origin, which
 *  Vite proxies to the Python backend. */

async function get(path) {
  const res = await fetch(path);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* response had no JSON body; keep the status message */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const listNetworks = () => get("/api/networks");
export const getNetwork = (id) => get(`/api/networks/${id}`);

export async function validateNetwork(network) {
  const res = await fetch("/api/networks/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(network),
  });
  if (!res.ok) {
    // A 422 means the JSON did not even match the expected shape.
    if (res.status === 422) {
      const body = await res.json().catch(() => null);
      const first = body?.detail?.[0];
      const where = first?.loc ? first.loc.slice(1).join(" → ") : "the file";
      throw new Error(`${where}: ${first?.msg ?? "wrong shape for a network file"}`);
    }
    throw new Error(`Validation request failed (${res.status})`);
  }
  return res.json();
}

// --- solving -----------------------------------------------------------------

export async function startSolve(config) {
  const res = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    // 422 is pydantic rejecting the shape; its detail is an array, not a string.
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((d) => `${d.loc?.slice(1).join(".")}: ${d.msg}`).join("; ")
      : body?.detail;
    throw new Error(detail || `Could not start the solve (${res.status})`);
  }
  return res.json();
}

export const getJob = (id) => get(`/api/jobs/${id}`);
export const getJobResult = (id) => get(`/api/jobs/${id}/result`);
