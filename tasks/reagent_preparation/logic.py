
from system.task import BaseTaskLogic


class ReagentPreparationTask(BaseTaskLogic):
    """Pure AI chat Task, no hardware dependencies."""

    def __init__(self):
        super().__init__()

    def start(self):
        print("Starting Reagent Preparation Task...")
        super().start()

    def stop(self):
        super().stop()

    def get_status(self):
        return {
            "mode": "READY",
            "message": "Reagent Preparation Assistant Ready",
        }


if __name__ == "__main__":
    ReagentPreparationTask().run_as_main()
