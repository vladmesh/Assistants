        assert isinstance(
            assistant_instance.tools[0], TimeToolWrapper
        )  # Check for correct tool type
        assert (
            assistant_instance.tools[0].name == "current_time"
        )  # Check name from ToolModel used by factory
        assert assistant_instance.compiled_graph is not None  # Check if graph is compiled
        # Check default system prompt if not overridden
        assert assistant_instance.system_prompt == "You are a test assistant." 