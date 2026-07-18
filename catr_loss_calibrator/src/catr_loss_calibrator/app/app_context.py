from __future__ import annotations

from dataclasses import dataclass

from catr_loss_calibrator.project.config import ProjectConfig


@dataclass(frozen=True)
class AppContext:
    project_config: ProjectConfig = ProjectConfig()

