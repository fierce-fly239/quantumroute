import { Card, Note, PageHead, Stat } from "../components/ui.jsx";
import { Check, Cpu, Sparkles, Users, Zap } from "../components/icons.jsx";

/** Who built this. Only facts: the team, the problem statement, the stack.
 *  Names as Vrishank gave them on 18 Sep; no roles, by his choice. */

const TEAM = {
  name: "Cyber Pookies",
  college: "Vedam School of Technology, Gurugram",
  ps: "SIH26137",
  psTitle: "Quantum-inspired vehicle route optimization",
  org: "Egreen Quanta",
  theme: "Transportation & Logistics",
  members: [
    "Anant Saboo", "Vrishank Kuthiala", "Vedika Seth",
    "Yuvval Bhasin", "Akshay Jaiswal", "Harshit Aggarwal",
  ],
};

const TONES = ["mint", "peach", "lilac", "butter", "blue", "mint"];

export default function Team() {
  return (
    <div className="page">
      <PageHead
        eyebrow="workspace / team"
        status="smart india hackathon 2026"
        title="Team"
        lede={`${TEAM.name} · ${TEAM.college}. Problem statement ${TEAM.ps} from ${TEAM.org}, theme ${TEAM.theme}.`}
      />

      <div className="stats stats-3">
        <Stat icon={<Users />} label="team" value={TEAM.name} foot={TEAM.college.split(",")[0]} tone="mint" delay={1} />
        <Stat icon={<Zap />} label="problem statement" value={TEAM.ps} foot={TEAM.org} tone="peach" delay={1} />
        <Stat icon={<Cpu />} label="stack" value="FastAPI + React" foot="python · vite · leaflet" tone="lilac" delay={1} />
      </div>

      <div className="two-col-narrow">
        <Card title="Members" sub="six of us" className="rise rise-2">
          <div className="team-grid">
            {TEAM.members.map((name, i) => (
              <div key={name} className="member">
                <span className={`member-avatar tone-${TONES[i % TONES.length]}`}>
                  {name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
                </span>
                <span className="row-title">{name}</span>
              </div>
            ))}
          </div>
        </Card>

        <Note eyebrow="what is real on this site" icon={<Sparkles />} title="Everything you can click.">
          <p>
            Every map, number and curve comes from the API on this machine: 8 endpoints, an in-memory job
            queue, a quantum-inspired particle swarm and its classical baseline, an exact solver for the small
            instance, and 94 tests. Nothing on any page is typed in.
          </p>
        </Note>
      </div>

      <Card title={TEAM.psTitle} sub={`${TEAM.ps} · ${TEAM.org}`} className="mt" icon={<Check />}>
        <p className="card-lede" style={{ marginBottom: 0 }}>
          Model the transportation network as a weighted directed graph, optimize delivery routes for a fleet with
          a quantum-inspired metaheuristic, show convergence, and benchmark against a classical method on
          real-time or simulated traffic. This app does each of those in turn: Network, Configure, Run, Results.
        </p>
      </Card>
    </div>
  );
}
