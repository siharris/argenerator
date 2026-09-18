# argenerator

Render architecture roadmaps — a time axis across the top, capability domains down the
side, forking initiative tracks with milestones and deliveries — from a hand-edited YAML
file to a PowerPoint slide.

No LLM/AI is involved: this is a deterministic renderer. The YAML file is the durable
source of truth (roadmap-as-code); re-run the CLI any time you edit it.

## Install

```
pip install -e .
```

## Usage

```
argenerator render examples/roadmap.yaml -o roadmap.pptx
argenerator validate examples/roadmap.yaml
```

Options for `render`:

- `--icons DIR` — directory of domain icon images (PNG), overriding the roadmap's
  `icon_dir` and the default `icons/` folder next to the YAML file. Falls back to a
  bundled default gear icon if a domain's `icon` isn't found.
- `--theme FILE` — a YAML/JSON file of colour/font overrides, merged over the built-in
  palette. See `argenerator/theme.py` for all overridable fields.

## Roadmap YAML shape

```yaml
title: "Architecture Roadmap"
timeline:
  start: "FY27.Q1"
  end: "FY28.Q4"
domains:
  - name: "Strategic Products"
    icon: "gear.png"        # looked up in the resolved icon directory
    tracks:
      - name: "Agentforce Rollout"
        events:
          - {type: start, period: "FY27.Q1", label: "Kickoff"}
          - {type: milestone, period: "FY27.Q3", label: "Pilot Live", highlight: true}
          - {type: delivery, period: "FY28.Q2", label: "GA Release"}
dependencies:
  - from_event: "strategic_products.agentforce_rollout.<event_id>"
    to_event: "other_domain.other_track.<event_id>"
    style: dashed
    label: "enables"
```

- `type` is one of `start` (label only, no marker), `milestone` (hollow circle), or
  `delivery` (filled square).
- `id` fields are optional and auto-generated from names/labels if omitted; set them
  explicitly when you need a stable reference for `dependencies`.
- The fork point where a domain's tracks branch out is derived automatically from the
  domain's track list — it isn't authored in the YAML.

See `examples/roadmap.yaml` for a complete example.

## Tests

```
pytest
```
