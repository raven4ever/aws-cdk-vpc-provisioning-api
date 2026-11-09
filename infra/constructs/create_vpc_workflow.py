from constructs import Construct


class CreateWorkflow(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
    ) -> None:
        super().__init__(scope, id)
