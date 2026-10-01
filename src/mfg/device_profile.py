"""Device Profile — load model YAML and render CLI templates."""
import yaml
from pathlib import Path

# src/mfg/ -> src -> repo root -> config/profiles
PROFILES_DIR = Path(__file__).parent.parent.parent / "config" / "profiles"


class DeviceProfile:
    """Load a device profile YAML and render command templates."""

    def __init__(self, model_name):
        path = PROFILES_DIR / f"{model_name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        self.name = data.get("name", model_name)
        self.type = data.get("type", "")
        self.ports = data.get("ports", {})
        self.commands = data.get("commands", {})
        self.api = data.get("api", "")

    @property
    def port_count(self):
        eth = self.ports.get("ethernet", {})
        if isinstance(eth, dict):
            return eth.get("count", 0)
        if isinstance(eth, list):
            return len(eth)
        return 0

    def render(self, cmd_key, **kwargs):
        """Render a command template with given parameters. Returns list of lines."""
        template = self.commands.get(cmd_key)
        if not template:
            raise KeyError(f"Command '{cmd_key}' not in profile '{self.name}'")
        rendered = template.format(**kwargs)
        return [line for line in rendered.strip().splitlines() if line.strip()]

    def to_dict(self):
        """Serialize for API response."""
        return {
            "name": self.name,
            "type": self.type,
            "port_count": self.port_count,
            "ports": self.ports,
            "commands": list(self.commands.keys()),
        }


def list_profiles():
    """Return all available profile names."""
    return [p.stem for p in PROFILES_DIR.glob("*.yaml")]


def load_profile(model_name):
    """Load and return a DeviceProfile instance."""
    return DeviceProfile(model_name)
