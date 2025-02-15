# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_fmu_proxy_interface.ipynb.

# %% auto 0
__all__ = ['logger', 'ch', 'formatter', 'PROXY_HEADER', 'PROXY_HEADER_OLD', 'PATH_TO_FMU_PROXY_JAR', 'NetworkEndpoint',
           'get_run_arguments_for_proxy_fmu', 'run_proxy_fmu', 'check_local_port', 'get_local_open_port',
           'check_java_version_for_fmu_proxy', 'DistributedSimulationProxyServer']

# %% ../nbs/04_fmu_proxy_interface.ipynb 3
import json
import logging
import os
from dataclasses import dataclass
from subprocess import Popen, PIPE, check_output, STDOUT
from typing import Dict, Union, Optional, List
import socket

# %% ../nbs/04_fmu_proxy_interface.ipynb 4
# Define logger
logger = logging.getLogger("__name__")
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)

logger.addHandler(ch)

PROXY_HEADER = "proxyfmu://"
PROXY_HEADER_OLD = "fmu-proxy://"

try:
    _MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _MODULE_PATH = os.path.dirname(os.path.abspath(""))

PATH_TO_FMU_PROXY_JAR = os.path.join(
    _MODULE_PATH, os.path.pardir, "osp_cosim", "win64", "bin_old", "fmu-proxy.jar"
)


@dataclass
class NetworkEndpoint:
    """Namedtuple class for a network endpoint"""

    address: str
    port: int = None

    def to_dict(self) -> Dict[str, Union[str, int]]:
        """Return dictionary form of the data"""
        return {"address": self.address, "port": self.port}

    def to_json(self) -> str:
        """Return json form of the data"""
        return json.dumps(self.to_dict())

    @property
    def network_string(self) -> str:
        """Returns a network string"""
        if self.port is None:
            return self.address
        return f"{self.address}:{self.port}"

    @property
    def is_local_host(self) -> bool:
        """Returns True if the address is localhost"""
        return self.address in ["localhost", "127.0.0.1"]


def get_run_arguments_for_proxy_fmu(port: int, fmu_path: str, for_package: bool = False) -> List[str]:
    """Get the arguments for running the proxy fmu"""
    if for_package:
        path_to_jar = os.path.join("bin", os.path.basename(PATH_TO_FMU_PROXY_JAR))
        path_to_fmu = os.path.basename(fmu_path)
    else:
        path_to_jar = PATH_TO_FMU_PROXY_JAR
        path_to_fmu = fmu_path
    return ["java", "-jar", path_to_jar, "-thrift/tcp", str(port), path_to_fmu]


def run_proxy_fmu(port: int, fmu_path: str) -> Popen:
    """Run the proxy fmu"""
    args = get_run_arguments_for_proxy_fmu(port=port, fmu_path=fmu_path)
    logger.info(f"Running local proxy server: {' '.join(args)}")
    return Popen(args=args, shell=True, stdout=PIPE, stderr=PIPE)


def check_local_port(port: int) -> bool:
    """Check if a local port is available"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def get_local_open_port(start_port: int) -> int:
    """Get a local open port"""
    port = start_port
    while not check_local_port(port):
        port += 1
    return port


def check_java_version_for_fmu_proxy():
    """Check if the java version is at least 1.8"""
    try:
        java_version = check_output(["java", "-version"], stderr=STDOUT).decode("utf-8")
    except FileNotFoundError as exc:
        raise TypeError(
            "Java runtime not found. Please install Java runtime 1.8.0_281 or upto 1.8.0.333."
        ) from exc
    index_start = java_version.find('"')
    index_end = java_version.find('"', index_start + 1)
    java_version1, java_version2 = java_version[index_start + 1 : index_end].split("_")
    if java_version1 != "1.8.0":
        raise TypeError("Java version must be 1.8.0_333 or lower.")
    if int(java_version2) > 333:
        raise TypeError("Java version must be 1.8.0_333 or lower.")


class DistributedSimulationProxyServer:
    """Class for handling distributed simulation proxy server"""

    def __init__(
        self,
        file_path_fmu: Optional[str] = None,
        endpoint: NetworkEndpoint = NetworkEndpoint(address="localhost", port=9090),
        guid: Optional[str] = None,
        source_text: Optional[str] = None,
    ):
        """Constructor for the class"""
        if source_text is not None:
            # source_text should be in the following form: "address:port?file=path/to/fmu" for
            # new cosim (>0.4.0) and "address:port?guid=xxxx" for old cosim (<0.4.0)
            # if address is localhost, port may be missing
            address_port, query = source_text.split("?")
            address, port = (
                address_port.split(":") if ":" in address_port else (address_port, None)
            )
            port = int(port) if port is not None else None
            endpoint = NetworkEndpoint(address=address, port=port)
            if "file=" in query:
                file_path_fmu = query.split("=")[1]
                guid = None
            elif "guid=" in query:
                file_path_fmu = None
                guid = query.split("=")[1]
        self.guid = guid
        self.endpoint = endpoint
        self.file_path_fmu = file_path_fmu

    @property
    def has_guid(self) -> bool:
        """Returns True if the proxy server is for new cosim (>0.4.0)"""
        return self.guid is not None

    @property
    def _query_string(self) -> str:
        """Returns the query string for the endpoint"""
        if not self.has_guid:
            return f"file={self.file_path_fmu}"
        return f"guid={self.guid}"

    @property
    def endpoint_str(self):
        """Returns the end point for a system structure file"""
        if not self.has_guid:
            return f"{PROXY_HEADER}{self.endpoint.network_string}?{self._query_string}"
        return f"{PROXY_HEADER_OLD}{self.endpoint.network_string}?{self._query_string}"

    def run_local_fmu_proxy(self, fmu_path: str = None) -> Optional[Popen]:
        """Runs the local fmu proxy"""
        if not self.has_guid:
            raise TypeError("GUID missing for the proxy server")
        else:
            fmu_path = fmu_path if fmu_path is not None else self.file_path_fmu
            check_java_version_for_fmu_proxy()
            return run_proxy_fmu(port=self.endpoint.port, fmu_path=fmu_path)

    def get_local_fmu_proxy_command(self, fmu_path: str = None, for_package: bool = False) -> List[str]:
        """Returns the command for running the local fmu proxy"""
        if not self.has_guid:
            raise TypeError("GUID missing for the proxy server")
        else:
            fmu_path = fmu_path if fmu_path is not None else self.file_path_fmu
            return get_run_arguments_for_proxy_fmu(
                port=self.endpoint.port, fmu_path=fmu_path, for_package=for_package
            )
