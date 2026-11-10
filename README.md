# 3D Print Figure

Turn a reference image into a versioned Blender model and, after print checks and approval, an STL. Two Agent Skills coordinate image generation, Tencent Hunyuan 3D, and Blender.

[简体中文](README.zh-CN.md) · [Changelog](CHANGELOG.md) · [License](LICENSE)

| Skill | Role | Installed under the project root |
| --- | --- | --- |
| [3d-print-figure](SKILL.md) | DSH coordinates requirements, reviews, Hunyuan, and approval checkpoints. | `.dsh/skills/3d-print-figure/` |
| [3d-print-blender](codex-skill/SKILL.md) | Codex reviews prompts and images, generates views, and runs Blender stages. | `.agents/skills/3d-print-blender/` |

## Install v1.0.0

Use Windows 10 or 11, Windows PowerShell 5.1, Git, Python with Pillow, and Node.js 22 or later. The full image-to-model workflow also needs a DSH runtime with Agent Skills support, Codex CLI with image generation, Blender 5.x, and an Edge or Chrome session with a Hunyuan 3D account. Blender can run in the background or through an already configured Blender MCP connection.

```powershell
git clone --branch v1.0.0 --single-branch https://github.com/RTD-com/3d-print-figure.git
Set-Location 3d-print-figure
$workdir = "<your working directory>"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -ProjectRoot $workdir
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/preflight.ps1 -Workdir $workdir
```

Run the installer from a Git checkout. It installs two self-contained packages and records the source commit and file hashes. Use `-Update` to replace an existing installation intentionally. For user-level installation, use `-Scope user` and check that both runtimes discover their skills.

## Start a project

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/init_project.ps1 -Workdir $workdir -Name "Sample figure" -ImagePath "<reference image>"
```

Open DSH in your working directory and ask it to use `3d-print-figure` for the new project. The [workflow guide](references/00-workflow.md) describes each stage, its inputs, and how to resume.

1. Review the requirements and confirm the dimensions and reference image.
2. Approve eight orthographic views. The front and side views establish volume and proportions first.
3. Check the Hunyuan upload preview and confirm credit use before generation. If you already have a GLB or need to download one manually, hand it off at the [Blender stage](references/40-blender-mcp.md).
4. Review the initial model and each repair in Blender. Approval to export is tied to the hash of the final Blender file.
5. Review the final STL and its [print checks](references/60-printing.md). Export requires measurements for self-intersection and minimum wall thickness.

The project is created under `手办/` in your working directory. Keep that directory and browser diagnostics private. Share reference images with Codex or Hunyuan only with permission. See the [security policy](SECURITY.md) for handling logs, signed URLs, and browser profiles.

## Verification

The [verification scope](docs/validation-matrix.md) distinguishes the offline checks from the live web, Blender, slicing, and physical-print checks that still require validation. The first public release is a versioned workflow and toolset.

For local checks and contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md). Source code and skill documentation are under the [MIT License](LICENSE).
