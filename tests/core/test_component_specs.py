"""Fondant component specs test."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fondant.core.component_spec import (
    ComponentSpec,
    KubeflowComponentSpec,
)
from fondant.core.exceptions import InvalidComponentSpec
from fondant.core.schema import Type

component_specs_path = Path(__file__).parent / "examples/component_specs"


@pytest.fixture()
def valid_fondant_schema() -> dict:
    with open(component_specs_path / "valid_component.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture()
def valid_fondant_schema_no_args() -> dict:
    with open(component_specs_path / "valid_component_no_args.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture()
def valid_kubeflow_schema() -> dict:
    with open(component_specs_path / "kubeflow_component.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture()
def invalid_fondant_schema() -> dict:
    with open(component_specs_path / "invalid_component.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture()
def valid_fondant_schema_generic_consumes() -> dict:
    with open(component_specs_path / "generic_consumes.yaml") as f:
        return yaml.safe_load(f)


@pytest.fixture()
def valid_fondant_schema_generic_produces() -> dict:
    with open(component_specs_path / "generic_produces.yaml") as f:
        return yaml.safe_load(f)


@patch("pkgutil.get_data", return_value=None)
def test_component_spec_pkgutil_error(mock_get_data):
    """Test that FileNotFoundError is raised when pkgutil.get_data returns None."""
    with pytest.raises(FileNotFoundError):
        ComponentSpec("example_component.yaml")


def test_component_spec_validation(valid_fondant_schema, invalid_fondant_schema):
    """Test that the component spec is validated correctly on instantiation."""
    ComponentSpec(valid_fondant_schema)
    with pytest.raises(InvalidComponentSpec):
        ComponentSpec(invalid_fondant_schema)


def test_component_spec_load_from_file(valid_fondant_schema, invalid_fondant_schema):
    """Test that the component spec is validated correctly on instantiation."""
    ComponentSpec.from_file(component_specs_path / "valid_component.yaml")
    with pytest.raises(InvalidComponentSpec):
        ComponentSpec.from_file(component_specs_path / "invalid_component.yaml")


def test_attribute_access(valid_fondant_schema):
    """
    Test that attributes can be accessed as expected:
    - Fixed properties should be accessible as an attribute
    - Dynamic properties should be accessible by lookup.
    """
    fondant_component = ComponentSpec(valid_fondant_schema)

    assert fondant_component.name == "Example component"
    assert fondant_component.description == "This is an example component"
    assert fondant_component.consumes["images"].type == Type("binary")
    assert fondant_component.consumes["embeddings"].type == Type.list(
        Type("float32"),
    )


def test_kfp_component_creation(valid_fondant_schema, valid_kubeflow_schema):
    """Test that the created kubeflow component matches the expected kubeflow component."""
    fondant_component = ComponentSpec(valid_fondant_schema)
    kubeflow_component = fondant_component.kubeflow_specification
    with open("./new_spec", "w") as f:
        import json

        json.dump(kubeflow_component._specification, f)
    assert kubeflow_component._specification == valid_kubeflow_schema


def test_component_spec_no_args(valid_fondant_schema_no_args):
    """Test that a component spec without args is supported."""
    fondant_component = ComponentSpec(valid_fondant_schema_no_args)

    assert fondant_component.name == "Example component"
    assert fondant_component.description == "This is an example component"
    assert fondant_component.args == fondant_component.default_arguments


def test_component_spec_to_file(valid_fondant_schema):
    """Test that the ComponentSpec can be written to a file."""
    component_spec = ComponentSpec(valid_fondant_schema)

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "component_spec.yaml")
        component_spec.to_file(file_path)

        with open(file_path) as f:
            written_data = yaml.safe_load(f)

        # check if the written data is the same as the original data
        assert written_data == valid_fondant_schema


def test_kubeflow_component_spec_to_file(valid_kubeflow_schema):
    """Test that the KubeflowComponentSpec can be written to a file."""
    kubeflow_component_spec = KubeflowComponentSpec(valid_kubeflow_schema)

    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "kubeflow_component_spec.yaml")
        kubeflow_component_spec.to_file(file_path)

        with open(file_path) as f:
            written_data = yaml.safe_load(f)

        # check if the written data is the same as the original data
        assert written_data == valid_kubeflow_schema


def test_component_spec_repr(valid_fondant_schema):
    """Test that the __repr__ method of ComponentSpec returns the expected string."""
    fondant_component = ComponentSpec(valid_fondant_schema)
    expected_repr = f"ComponentSpec({valid_fondant_schema!r})"
    assert repr(fondant_component) == expected_repr


def test_kubeflow_component_spec_repr(valid_kubeflow_schema):
    """Test that the __repr__ method of KubeflowComponentSpec returns the expected string."""
    kubeflow_component_spec = KubeflowComponentSpec(valid_kubeflow_schema)
    expected_repr = f"KubeflowComponentSpec({valid_kubeflow_schema!r})"
    assert repr(kubeflow_component_spec) == expected_repr


def test_component_spec_generic_consumes(valid_fondant_schema_generic_consumes):
    """Test that a component spec with generic consumes is detected."""
    component_spec = ComponentSpec(valid_fondant_schema_generic_consumes)
    assert component_spec.is_generic("consumes") is True
    assert component_spec.is_generic("produces") is False


def test_component_spec_generic_produces(valid_fondant_schema_generic_produces):
    """Test that a component spec with generic produces is detected."""
    component_spec = ComponentSpec(valid_fondant_schema_generic_produces)
    assert component_spec.is_generic("consumes") is False
    assert component_spec.is_generic("produces") is True
