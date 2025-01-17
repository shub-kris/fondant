import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from fondant.pipeline import Pipeline
from fondant.pipeline.runner import (
    DockerRunner,
    KubeflowRunner,
    SagemakerRunner,
    VertexRunner,
)

VALID_PIPELINE = Path("./tests/pipeline/examples/pipelines/compiled_pipeline/")

PIPELINE = Pipeline(
    name="testpipeline",
    description="description of the test pipeline",
    base_path="/foo/bar",
)


def test_docker_runner():
    """Test that the docker runner while mocking subprocess.call."""
    with mock.patch("subprocess.call") as mock_call:
        DockerRunner().run("some/path")
        mock_call.assert_called_once_with(
            [
                "docker",
                "compose",
                "-f",
                "some/path",
                "up",
                "--build",
                "--pull",
                "always",
                "--remove-orphans",
            ],
        )


def test_docker_runner_from_pipeline():
    with mock.patch("subprocess.call") as mock_call:
        DockerRunner().run(PIPELINE)
        mock_call.assert_called_once_with(
            [
                "docker",
                "compose",
                "-f",
                ".fondant/compose.yaml",
                "up",
                "--build",
                "--pull",
                "always",
                "--remove-orphans",
            ],
        )


class MockKfpClient:
    def __init__(self, host):
        self.host = host
        self._experiments = {"Default": SimpleNamespace(experiment_id="123")}

    def get_experiment(self, experiment_name):
        try:
            return self._experiments[experiment_name]
        except KeyError:
            raise ValueError

    def create_experiment(self, experiment_name):
        self._experiments[experiment_name] = SimpleNamespace(experiment_id="456")
        return self.get_experiment(experiment_name)

    def run_pipeline(self, experiment_id, job_name, pipeline_package_path):
        return SimpleNamespace(run_id="xyz")


def test_kubeflow_runner():
    input_spec_path = str(VALID_PIPELINE / "kubeflow_pipeline.yml")
    with mock.patch(
        "kfp.Client",
        new=MockKfpClient,
    ):
        runner = KubeflowRunner(host="some_host")
        runner.run(input=input_spec_path)

        assert runner.client.host == "some_host"


def test_kubeflow_runner_new_experiment():
    input_spec_path = str(VALID_PIPELINE / "kubeflow_pipeline.yml")
    with mock.patch(
        "kfp.Client",
        new=MockKfpClient,
    ):
        runner = KubeflowRunner(host="some_host")
        runner.run(input=input_spec_path, experiment_name="NewExperiment")


def test_kfp_import():
    """Test that the kfp import throws the correct error."""
    with mock.patch.dict(sys.modules), mock.patch(
        "kfp.Client",
        new=MockKfpClient,
    ):
        # remove kfp from the modules
        sys.modules["kfp"] = None
        with pytest.raises(ImportError):
            _ = KubeflowRunner(host="some_host")


class MockKubeFlowCompiler:
    def compile(
        self,
        pipeline,
        output_path,
    ) -> None:
        with open(output_path, "w") as f:
            f.write("foo: bar")


def test_kubeflow_runner_from_pipeline():
    with mock.patch(
        "fondant.pipeline.runner.KubeFlowCompiler",
        new=MockKubeFlowCompiler,
    ), mock.patch(
        "fondant.pipeline.runner.KubeflowRunner._run",
    ) as mock_run, mock.patch(
        "kfp.Client",
        new=MockKfpClient,
    ):
        runner = KubeflowRunner(host="some_host")
        runner.run(
            input=PIPELINE,
        )

        mock_run.assert_called_once_with(
            ".fondant/kubeflow-pipeline.yaml",
            experiment_name="Default",
        )


def test_vertex_runner():
    input_spec_path = str(VALID_PIPELINE / "kubeflow_pipeline.yml")
    with mock.patch("google.cloud.aiplatform.init", return_value=None), mock.patch(
        "google.cloud.aiplatform.PipelineJob",
    ):
        runner = VertexRunner(project_id="some_project", region="some_region")
        runner.run(input=input_spec_path)

        # test with service account
        runner2 = VertexRunner(
            project_id="some_project",
            region="some_region",
            service_account="some_account",
        )
        runner2.run(input=input_spec_path)


def test_vertex_runner_from_pipeline():
    with mock.patch(
        "fondant.pipeline.runner.VertexCompiler",
        new=MockKubeFlowCompiler,
    ), mock.patch("fondant.pipeline.runner.VertexRunner._run") as mock_run, mock.patch(
        "google.cloud.aiplatform.init",
        return_value=None,
    ):
        runner = VertexRunner(project_id="some_project", region="some_region")
        runner.run(
            input=PIPELINE,
        )

        mock_run.assert_called_once_with(".fondant/vertex-pipeline.yaml")


def test_sagemaker_runner(tmp_path_factory):
    with mock.patch("boto3.client", spec=True), tmp_path_factory.mktemp(
        "temp",
    ) as tmpdir:
        # create a small temporary spec file
        with open(tmpdir / "spec.json", "w") as f:
            f.write('{"pipelineInfo": {"name": "pipeline_1"}}')
        runner = SagemakerRunner()

        runner.run(
            input=tmpdir / "spec.json",
            pipeline_name="pipeline_1",
            role_arn="arn:something",
        )

        # check which methods were called on the client
        assert runner.client.method_calls == [
            mock.call.list_pipelines(PipelineNamePrefix="pipeline_1"),
            mock.call.update_pipeline(
                PipelineName="pipeline_1",
                PipelineDefinition='{"pipelineInfo": {"name": "pipeline_1"}}',
                RoleArn="arn:something",
            ),
            mock.call.start_pipeline_execution(
                PipelineName="pipeline_1",
                ParallelismConfiguration={"MaxParallelExecutionSteps": 1},
            ),
        ]

        # reset the mock and test the creation of a new pipeline
        runner.client.reset_mock()
        runner.client.configure_mock(
            **{"list_pipelines.return_value": {"PipelineSummaries": []}},
        )

        runner.run(
            input=tmpdir / "spec.json",
            pipeline_name="pipeline_1",
            role_arn="arn:something",
        )
        # here we expect the create_pipeline method to be called
        assert runner.client.method_calls == [
            mock.call.list_pipelines(PipelineNamePrefix="pipeline_1"),
            mock.call.create_pipeline(
                PipelineName="pipeline_1",
                PipelineDefinition='{"pipelineInfo": {"name": "pipeline_1"}}',
                RoleArn="arn:something",
            ),
            mock.call.start_pipeline_execution(
                PipelineName="pipeline_1",
                ParallelismConfiguration={"MaxParallelExecutionSteps": 1},
            ),
        ]


class MockSagemakerCompiler:
    def compile(
        self,
        pipeline,
        output_path,
        *,
        role_arn,
    ) -> None:
        with open(output_path, "w") as f:
            f.write("foo: bar")


def test_sagemaker_runner_from_pipeline():
    with mock.patch(
        "fondant.pipeline.runner.SagemakerCompiler",
        new=MockSagemakerCompiler,
    ), mock.patch("boto3.client", spec=True):
        runner = SagemakerRunner()
        runner.run(
            input=PIPELINE,
            pipeline_name=PIPELINE.name,
            role_arn="arn:something",
        )
