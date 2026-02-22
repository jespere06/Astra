import logging
from kubernetes import client, config
from src.config import settings

logger = logging.getLogger(__name__)

class K8sClient:
    def __init__(self):
        try:
            # Intentar cargar config in-cluster (producción) o kubeconfig (local)
            try:
                config.load_incluster_config()
            except config.ConfigException:
                try:
                    config.load_kube_config()
                except Exception:
                    logger.warning("No se pudo cargar configuración de K8s. Operando en modo mock.")
                    self.batch_v1 = None
                    return
                
            self.batch_v1 = client.BatchV1Api()
        except Exception as e:
            logger.error(f"Error inicializando cliente K8s: {e}")
            self.batch_v1 = None

    def create_training_job(self, job_name: str, tenant_id: str, dataset_uri: str, base_model: str):
        if not self.batch_v1:
            logger.warning("Cliente K8s no disponible. Saltando creación de Job (Modo Dev/Mock).")
            return

        # Definición del Job (Equivalente al YAML)
        container = client.V1Container(
            name="trainer",
            image=settings.TRAINER_IMAGE,
            command=["python", "train.py"],
            args=[
                "--tenant_id", tenant_id,
                "--dataset_uri", dataset_uri,
                "--base_model", base_model
            ],
            env=[
                client.V1EnvVar(name="MLFLOW_TRACKING_URI", value=settings.MLFLOW_URI),
                # Credenciales inyectadas via Secrets en el Cluster
                client.V1EnvVar(
                    name="AWS_ACCESS_KEY_ID",
                    value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(name="aws-creds", key="access_key"))
                ),
                client.V1EnvVar(
                    name="AWS_SECRET_ACCESS_KEY",
                    value_from=client.V1EnvVarSource(secret_key_ref=client.V1SecretKeySelector(name="aws-creds", key="secret_key"))
                )
            ],
            resources=client.V1ResourceRequirements(
                limits={"nvidia.com/gpu": "1"},
                requests={"memory": "8Gi", "cpu": "2000m"}
            )
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": "astra-trainer", "tenant": tenant_id}),
            spec=client.V1PodSpec(
                restart_policy="OnFailure",
                containers=[container],
                node_selector={"accelerator": "nvidia-gpu"},
                tolerations=[
                    client.V1Toleration(key="nvidia.com/gpu", operator="Exists", effect="NoSchedule")
                ]
            )
        )

        job_spec = client.V1JobSpec(
            template=template,
            backoff_limit=2,
            ttl_seconds_after_finished=3600
        )

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name=job_name, namespace=settings.K8S_NAMESPACE),
            spec=job_spec
        )

        try:
            response = self.batch_v1.create_namespaced_job(
                body=job,
                namespace=settings.K8S_NAMESPACE
            )
            logger.info(f"Job creado en K8s: {response.metadata.name}")
        except Exception as e:
            logger.error(f"Fallo creando Job en K8s: {e}")
            raise
