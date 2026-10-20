# Ema stack evidence

Reviewed 2026-10-20 using Ema's own public job postings. Hiring requirements indicate technologies sought or discussed; they are not a complete inventory of the company's production stack.

| Layer | Public evidence | Relay decision |
| --- | --- | --- |
| Backend languages | Platform and backend roles explicitly name Go and Python | Python for the initial runtime; Go only for a justified later service |
| API and storage | Backend role names FastAPI, PostgreSQL, REST/gRPC/GraphQL; also Redis and Elastic | FastAPI, typed schemas, PostgreSQL in team mode; SQLite locally |
| Workflow and events | Backend role names Temporal and Kafka | Temporal for durable workflows; Kafka only when event volume/consumer requirements justify it |
| Frontend | Backend role names React or Angular as relevant experience | React + TypeScript; this does not prove Ema uses our exact frontend combination |
| Infrastructure | Platform role names Kubernetes, Docker, Terraform, Helm, GitOps, cloud providers | Docker for reproducible services; remote infrastructure introduced by deployment need |
| Observability | Platform role names Prometheus, Grafana, OpenTelemetry and tracing | OpenTelemetry from the first live vertical slice; metrics/dashboards as services are added |
| ML training and serving | User-supplied job description lists TRL/veRL/OpenRLHF and vLLM/SGLang as useful experience, with SFT/DPO/GRPO/DAPO as methods to investigate | PyTorch/Transformers/TRL for a focused initial experiment; one serving backend, compared against alternatives when justified |
| Desktop | No desktop framework was established from these sources | Tauri and Rust are our desktop-specific choices, not attributed to Ema |

Sources:

- [Ema Platform Engineer](https://www.ema.ai/careers/jobs/748c829c-cb1d-48cf-90da-780593e89bea)
- [Ema Backend Engineer](https://www.ema.ai/careers/jobs/eb62df31-0370-447f-8cc6-707e79cbc9fa)
- [Ema Full Stack UK](https://www.ema.ai/careers/jobs/8207a75e-2762-4f5f-bb40-1fa168b918e0)
- [Ema core concepts](https://builder.ema.ai/builder/v2/core-concepts)
- ML/agent role: the complete description pasted by the user in this conversation.

The objective is a defensible desktop agent system with meaningful overlap in skills and mechanisms. Using every named technology would add complexity without establishing equivalent engineering quality.
