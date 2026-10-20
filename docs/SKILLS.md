# Imported engineering skills

Imported 2026-10-20 into the project-local `.agents/skills/` directory. There are 39 skill entry points and 373 source files including support files and upstream license notices. Every imported file matches its pinned upstream Git blob; `.agents/skills-lock.json` also stores SHA-256 hashes.

These files are usable as project guidance in this session and by an agent that reads this repository's AGENTS.md. This is not a claim of global ChatGPT Skills-page registration or automatic loading of every body. Read the routing table in AGENTS.md, then load the relevant skill and references for the task. No upstream installer or repository hook was executed.

The initial pass had read selected documents only. This import adds their actual local files and dependencies. Existing platform-provided Hugging Face skills remain available for future training work; they were not copied or replaced.

## Source inventory

| Local directory | Upstream source | Pinned commit | Files in skill |
| --- | --- | --- | --- |
| frontend-design | [anthropics/skills](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design) | `dbd4588f9e10` | 2 |
| mcp-builder | [anthropics/skills](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/mcp-builder) | `dbd4588f9e10` | 10 |
| ui-ux-pro-max | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4/.claude/skills/ui-ux-pro-max) | `56ea9cf174ed` | 73 |
| react-best-practices | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278/skills/react-best-practices) | `063bee94c3f4` | 76 |
| composition-patterns | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278/skills/composition-patterns) | `063bee94c3f4` | 14 |
| web-design-guidelines | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills/tree/063bee94c3f4df8453406c830b0a7df0f2860278/skills/web-design-guidelines) | `063bee94c3f4` | 1 |
| api-and-interface-design | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/tree/aeac41d4d005999432bb7312f7ff06383a91d59d/skills/api-and-interface-design) | `aeac41d4d005` | 1 |
| frontend-ui-engineering | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/tree/aeac41d4d005999432bb7312f7ff06383a91d59d/skills/frontend-ui-engineering) | `aeac41d4d005` | 1 |
| code-review-and-quality | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/tree/aeac41d4d005999432bb7312f7ff06383a91d59d/skills/code-review-and-quality) | `aeac41d4d005` | 1 |
| debugging-and-error-recovery | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/tree/aeac41d4d005999432bb7312f7ff06383a91d59d/skills/debugging-and-error-recovery) | `aeac41d4d005` | 1 |
| security-and-hardening | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/tree/aeac41d4d005999432bb7312f7ff06383a91d59d/skills/security-and-hardening) | `aeac41d4d005` | 2 |
| performance-optimization | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills/tree/aeac41d4d005999432bb7312f7ff06383a91d59d/skills/performance-optimization) | `aeac41d4d005` | 2 |
| codebase-design | [mattpocock/skills](https://github.com/mattpocock/skills/tree/5beb35b040e3de97e54fa9e386d7e42d15c295c2/skills/engineering/codebase-design) | `5beb35b040e3` | 4 |
| domain-modeling | [mattpocock/skills](https://github.com/mattpocock/skills/tree/5beb35b040e3de97e54fa9e386d7e42d15c295c2/skills/engineering/domain-modeling) | `5beb35b040e3` | 4 |
| tdd | [mattpocock/skills](https://github.com/mattpocock/skills/tree/5beb35b040e3de97e54fa9e386d7e42d15c295c2/skills/engineering/tdd) | `5beb35b040e3` | 4 |
| fastapi-patterns | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/fastapi-patterns) | `07971588f8ac` | 1 |
| postgres-patterns | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/postgres-patterns) | `07971588f8ac` | 1 |
| database-migrations | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/database-migrations) | `07971588f8ac` | 1 |
| rust-patterns | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/rust-patterns) | `07971588f8ac` | 1 |
| rust-testing | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/rust-testing) | `07971588f8ac` | 1 |
| eval-harness | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/eval-harness) | `07971588f8ac` | 1 |
| agent-security-hardening | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/agent-security-hardening) | `07971588f8ac` | 1 |
| windows-desktop-e2e | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/windows-desktop-e2e) | `07971588f8ac` | 1 |
| golang-patterns | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/golang-patterns) | `07971588f8ac` | 1 |
| golang-testing | [affaan-m/ECC](https://github.com/affaan-m/ECC/tree/07971588f8ac7a60080ba8c1b7920c9e8e733e7d/skills/golang-testing) | `07971588f8ac` | 1 |
| architecture-patterns | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/backend-development/skills/architecture-patterns) | `0874a27b17a2` | 3 |
| temporal-python-testing | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/backend-development/skills/temporal-python-testing) | `0874a27b17a2` | 5 |
| deployment-pipeline-design | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/cicd-automation/skills/deployment-pipeline-design) | `0874a27b17a2` | 3 |
| github-actions-templates | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/cicd-automation/skills/github-actions-templates) | `0874a27b17a2` | 1 |
| python-observability | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-observability) | `0874a27b17a2` | 2 |
| python-resilience | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/python-development/skills/python-resilience) | `0874a27b17a2` | 2 |
| accessibility-compliance | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/ui-design/skills/accessibility-compliance) | `0874a27b17a2` | 5 |
| design-system-patterns | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/ui-design/skills/design-system-patterns) | `0874a27b17a2` | 5 |
| eval-harness-first | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/llm-finetuning/skills/eval-harness-first) | `0874a27b17a2` | 3 |
| dataset-curation | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/llm-finetuning/skills/dataset-curation) | `0874a27b17a2` | 3 |
| preference-optimization | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/llm-finetuning/skills/preference-optimization) | `0874a27b17a2` | 2 |
| lora-qlora-recipes | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/llm-finetuning/skills/lora-qlora-recipes) | `0874a27b17a2` | 3 |
| checkpoint-promotion | [wshobson/agents](https://github.com/wshobson/agents/tree/0874a27b17a22e2b7c2e2bcd725768e0803cad06/plugins/llm-finetuning/skills/checkpoint-promotion) | `0874a27b17a2` | 2 |
| temporal-developer | [temporalio/skill-temporal-developer](https://github.com/temporalio/skill-temporal-developer/tree/3041178b597dddb1b54f49e5e73fbae644fba283/) | `3041178b597d` | 122 |

Six additional repository-level license files are in `.agents/upstream-licenses/`. Per-skill license files remain in their upstream locations. Preserve applicable attribution when redistributing. A missing root license is not evidence of unrestricted licensing.

## How to apply

1. Select skills by the feature's real concerns using AGENTS.md.
2. Read their full entry points and the referenced material necessary for the current task.
3. Resolve applicability against the project's platform, versions, and constraints. Treat snippets as examples to verify.
4. Implement a complete behavior and collect the evidence defined in docs/ENGINEERING_STANDARD.md.
5. Report which skills were applied, what changed, and what passed or remains unverified.

The guidance for this import was reviewed for applicability through metadata and core UI, architecture, agent-security, and promotion instructions. This does not mean every supporting reference or example has been audited. Special qualifications are recorded in docs/ENGINEERING_STANDARD.md.

## Verification

Run from the project root:

```powershell
python scripts/verify-skills.py
python .agents/skills/ui-ux-pro-max/scripts/search.py 'keyboard focus modal' --domain ux --json
python .agents/skills/ui-ux-pro-max/scripts/search.py 'state component composition' --stack react --json
```

Both search commands were executed and returned three relevant records each. They verify that the shipped search engine and data are usable; they do not verify the application's UI. The UI/UX Pro Max design-system generator was not used to redesign the application in this task.

The quality workflow now runs the integrity validator. This is an authored CI step, not evidence of a completed GitHub run. Source pinning detects unexpected byte changes; it does not establish that upstream guidance is correct.

## Updates and persistence

Keep upstream files unchanged. A deliberate update requires a new source commit, byte hashes, an applicability review, and validation. Review imported commands before execution. Do not let an upstream script expand session permissions, run external actions, or overwrite unrelated configuration.

This repository has local Git history for the imported files. No remote repository or global skill registration was configured. Project instructions should be read explicitly when reopening the project in an agent host that does not discover repository instructions.

