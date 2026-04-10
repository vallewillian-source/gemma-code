<div align="center">
<strong>gemma-code</strong>
</div>

# gemma-code

`gemma-code` is a fork of the upstream project adapted for offline, overnight software engineering workflows with local models from the Gemma 4 family.

The goal is to optimize for:

- Strong guidance and deterministic workflows for weaker local models
- Explicit tradeoffs in time and compute, with the agent designed to run unattended overnight
- A separate external LLM orchestrator and validator, starting with DeepSeekV3.2
- A narrow, opinionated setup that helps models build complete software systems instead of only partial fixes

[![Repository](https://img.shields.io/badge/Repo-gemma--code-blue?style=for-the-badge)](https://github.com/vallewillian-source/gemma-code)

> [!WARNING]
> This repository starts from **gemma-code v2**. The codebase still inherits upstream behavior until we replace it with gemma-specific orchestration, validation, and prompting policies.

`gemma-code` keeps the minimal core of the upstream project, but the product direction is different:

- **Local-first**: tuned for Gemma 4 models running on local hardware
- **Opinionated**: we will add guidelines and scaffolding so smaller models can still produce complete changes
- **Orchestrated**: an external validator/orchestrator handles quality control and higher-level steering
- **Unattended**: the agent is expected to run for long stretches without supervision

<details>

<summary>More motivation (for research)</summary>

`gemma-code` showed that a very small scaffold can still be useful. `gemma-code` takes that idea in a different direction: instead of optimizing for general model access, we are optimizing for local Gemma-family models that need stronger structure to succeed.

- **Keeps the shell-first interaction model** so the agent remains easy to inspect and debug
- **Preserves the linear trace** of actions and messages so validators can reason over the full trajectory
- **Assumes stronger prompt discipline** because weak models need more guardrails than the upstream project was designed to provide

This makes the project a good fit when the language model is not the most capable part of the stack and the surrounding workflow has to compensate for that.

</details>

<details>
<summary>More motivation (as a tool)</summary>

Some agents are overfitted research artifacts. Others are UI-heavy frontend monsters.

The `gemma-code` agent wants to be a hackable tool, not a black box.

- **Simple** enough to understand at a glance
- **Convenient** enough to use in daily workflows
- **Flexible** to extend

Unlike other agents (including our own [swe-agent](https://swe-agent.com/latest/)), it is radically simpler, because it:

- **Does not have any tools other than bash** — it doesn't even need to use the tool-calling interface of the LMs.
  Instead of implementing custom tools for every specific thing the agent might want to do, the focus is fully on the LM utilizing the shell to its full potential.
  Want it to do something specific like opening a PR?
  Just tell the LM to figure it out rather than spending time to implement it in the agent.
- **Executes actions with `subprocess.run`** — every action is completely independent (as opposed to keeping a stateful shell session running).
  This is [a big deal](https://gemma-code.com/latest/faq/#why-no-shell-session) for the stability of the agent, trust me.
- **Has a completely linear history** — every step of the agent just appends to the messages that are passed to the LM in the next step and that's it.
  This is great for debugging and understanding what the LM is prompted with.

</details>

<details>
<summary>Should I use gemma-code or the upstream project?</summary>

Use `gemma-code` if you want a fork that is intentionally opinionated for local Gemma 4 workflows and an external DeepSeekV3.2 validator/orchestrator.

Use the upstream project if you want the original docs, defaults, and model support.

At this stage, `gemma-code` still inherits the upstream CLI surface and many of the original docs, so the main difference is the project direction and the README framing rather than a new runtime API.

</details>

<table>
<tr>
<td width="50%">
<a href="https://gemma-code.com/latest/usage/mini/"><strong>CLI</strong></a> (<code>gemma-code</code>)
</td>
<td>
<a href="https://gemma-code.com/latest/usage/swebench/"><strong>Batch inference</strong></a>
</td>
</tr>
<tr>
<td width="50%">

![mini](https://github.com/SWE-agent/swe-agent-media/blob/main/media/mini/gif/mini.gif?raw=true)

</td>
<td>

![swebench](https://github.com/SWE-agent/swe-agent-media/blob/main/media/mini/gif/swebench.gif?raw=true)

</td>
</tr>
<tr>
<td>
<a href="https://gemma-code.com/latest/usage/inspector/"><strong>Trajectory browser</strong></a>
</td>
<td>
<a href="https://gemma-code.com/latest/advanced/cookbook/"><strong>Python bindings</strong></a>
</td>
</tr>
<tr>
<td>

![inspector](https://github.com/SWE-agent/swe-agent-media/blob/main/media/mini/gif/inspector.gif?raw=true)

</td>
<td>

```python
agent = DefaultAgent(
    LitellmModel(model_name=...),
    LocalEnvironment(),
)
agent.run("Write a sudoku game")
```

</td>
</tr>
</table>

## Let's get started!

**Option 1:** If you just want to try out the CLI (package installed in anonymous virtual environment)

```bash
pip install uv && uvx gemma-code
# or
pip install pipx && pipx ensurepath && pipx run gemma-code
```

**Option 2:** Install CLI & python bindings in current environment

```bash
pip install gemma-code
gemma-code  # run the CLI
```

**Option 3:** Install from source (developer setup)

```bash
git clone https://github.com/vallewillian-source/gemma-code.git
cd gemma-code && pip install -e .
gemma-code  # run the CLI
```

Read more in the project [documentation](https://gemma-code.com/latest/):

* [Quick start guide](https://gemma-code.com/latest/quickstart/)
* [Using the `gemma-code` CLI](https://gemma-code.com/latest/usage/mini/)
* [Global configuration](https://gemma-code.com/latest/advanced/global_configuration/)
* [Yaml configuration files](https://gemma-code.com/latest/advanced/yaml_configuration/)
* [Power up with the cookbook](https://gemma-code.com/latest/advanced/cookbook/)
* [FAQ](https://gemma-code.com/latest/faq/)
* [Contribute!](https://gemma-code.com/latest/contributing/)

## Attribution

If you found this work helpful, please consider citing the [SWE-agent paper](https://arxiv.org/abs/2405.15793) in your work:

```bibtex
@inproceedings{yang2024sweagent,
  title={{SWE}-agent: Agent-Computer Interfaces Enable Automated Software Engineering},
  author={John Yang and Carlos E Jimenez and Alexander Wettig and Kilian Lieret and Shunyu Yao and Karthik R Narasimhan and Ofir Press},
  booktitle={The Thirty-eighth Annual Conference on Neural Information Processing Systems},
  year={2024},
  url={https://arxiv.org/abs/2405.15793}
}
```

Our other projects:

<div align="center">
  <a href="https://github.com/SWE-agent/SWE-agent"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/sweagent_logo_text_below.svg" alt="SWE-agent" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-agent/SWE-ReX"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swerex_logo_text_below.svg" alt="SWE-ReX" height="120px"></a>
   &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/SWE-bench"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swebench_logo_text_below.svg" alt="SWE-bench" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/SWE-smith"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/swesmith_logo_text_below.svg" alt="SWE-smith" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/codeclash-ai/codeclash"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/codeclash_logo_text_below.svg" alt="CodeClash" height="120px"></a>
  &nbsp;&nbsp;
  <a href="https://github.com/SWE-bench/sb-cli"><img src="https://raw.githubusercontent.com/SWE-agent/swe-agent-media/refs/heads/main/media/logos_banners/sbcli_logo_text_below.svg" alt="sb-cli" height="120px"></a>
</div>
