"""
src/chaos_playbook_engine/agents/chaos_agent_universal.py

VERSIÓN ARREGLADA: _should_inject_chaos() con seed variability

Este es el archivo COMPLETO que debes copiar a:
src/chaos_playbook_engine/agents/chaos_agent_universal.py

CAMBIO CRÍTICO:
- _should_inject_chaos() ahora varía el seed en cada llamada
- Sin esto, random.Random(42).random() SIEMPRE devuelve 0.3716
- Con esto, cada llamada genera un número aleatorio diferente
"""

import os
import random
import asyncio
import json
import yaml
import requests
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ChaosAgentConfig:
    """Configuration for ChaosAgent."""
    
    openapi_spec_url: str
    default_failure_rate: float = 0.0
    default_seed: int = 42
    error_weights: Dict[str, int] = field(
        default_factory=lambda: {
            "400": 40,  # Bad Request
            "404": 30,  # Not Found
            "422": 20,  # Validation
            "500": 10,  # Server Error
        }
    )
    mock_success_enabled: bool = True
    mock_list_size: int = 5
    
    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'ChaosAgentConfig':
        """Load configuration from YAML file."""
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        chaos_config = data.get('chaos_agent', {})
        return cls(
            openapi_spec_url=chaos_config.get('openapi_spec_url'),
            default_failure_rate=chaos_config.get('default_failure_rate', 0.0),
            default_seed=chaos_config.get('default_seed', 42),
            error_weights=chaos_config.get('error_weights', {
                "400": 40, "404": 30, "422": 20, "500": 10
            }),
            mock_success_enabled=chaos_config.get('mock_success_enabled', True),
            mock_list_size=chaos_config.get('mock_list_size', 5),
        )


class ChaosAgent:
    """Generic Chaos Agent that simulates OpenAPI 3.0 APIs."""
    
    def __init__(self, config: ChaosAgentConfig):
        """Initialize ChaosAgent with configuration."""
        self.config = config
        self.spec = self.load_openapi_spec(config.openapi_spec_url)
        self.base_url = self.extract_base_url(self.spec)
        self.endpoints = self.parse_endpoints(self.spec)
        self.chaos_strategies = self.build_chaos_strategies(self.spec)
        
        print(f"📥 Loading OpenAPI spec from: {config.openapi_spec_url}")
        print(f"✅ ChaosAgent initialized:")
        print(f"   API: {self.spec.get('info', {}).get('title', 'Unknown')}")
        print(f"   Base URL: {self.base_url}")
        print(f"   Endpoints: {len(self.endpoints)}")
        print(f"   Error codes: {sum(len(v) for v in self.chaos_strategies.values())}")
    
    def load_openapi_spec(self, spec_url: str) -> dict:
        """Load OpenAPI 3.0 JSON from URL or file path."""
        if spec_url.startswith('http'):
            response = requests.get(spec_url, timeout=10)
            response.raise_for_status()
            return response.json()
        else:
            with open(spec_url, 'r') as f:
                return json.load(f)
    
    def extract_base_url(self, spec: dict) -> str:
        """Extract base URL from OpenAPI spec."""
        servers = spec.get('servers', [])
        if servers:
            return servers[0].get('url', 'http://localhost')
        return 'http://localhost'
    
    def parse_endpoints(self, spec: dict) -> Dict[str, Dict[str, Any]]:
        """Parse endpoints from OpenAPI spec."""
        endpoints = {}
        for path, methods in spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    continue
                
                operation_id = operation.get('operationId')
                if not operation_id:
                    operation_id = f"{method.upper()}_{path}".replace('/', '_')
                
                endpoints[operation_id] = {
                    'path': path,
                    'method': method.upper(),
                    'parameters': operation.get('parameters', []),
                    'requestBody': operation.get('requestBody'),
                    'responses': operation.get('responses', {}),
                    'summary': operation.get('summary', ''),
                    'description': operation.get('description', ''),
                }
        
        return endpoints
    
    def build_chaos_strategies(self, spec: dict) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Extract error codes from OpenAPI spec."""
        strategies = {}
        
        for path, methods in spec.get('paths', {}).items():
            for method, operation in methods.items():
                if method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    continue
                
                operation_id = operation.get('operationId')
                if not operation_id:
                    operation_id = f"{method.upper()}_{path}".replace('/', '_')
                
                strategies[operation_id] = {}
                
                for status_code, response_spec in operation.get('responses', {}).items():
                    if not status_code.startswith(('4', '5')):
                        continue
                    
                    error_message = response_spec.get('description', 'No description')
                    strategies[operation_id][status_code] = {
                        'message': error_message,
                        'http_method': method.upper(),
                        'path': path,
                    }
        
        return strategies
    
    def _should_inject_chaos(self, failure_rate: float, seed: int) -> bool:
        """
        Deterministically decide whether to inject chaos.
        
        ✅ FIXED: Varía el seed en cada llamada
        Antes: random.Random(42).random() = 0.3716 (siempre igual)
        Ahora: random.Random(43).random() = X, random.Random(44).random() = Y, etc.
        """
        if failure_rate <= 0.0:
            return False
        if failure_rate >= 1.0:
            return True
        
        # ✅ VARIAR EL SEED EN CADA LLAMADA
        self._call_counter = getattr(self, '_call_counter', 0) + 1
        varied_seed = seed + self._call_counter
        
        rng = random.Random(varied_seed)
        result = rng.random() < failure_rate
        
        return result
    
    def select_error_code(self, tool_name: str, seed: int) -> str:
        """Select which error code to inject for this tool."""
        if tool_name not in self.chaos_strategies:
            return "400"
        
        available_errors = list(self.chaos_strategies[tool_name].keys())
        if not available_errors:
            return "400"
        
        weights = []
        for code in available_errors:
            weight = self.config.error_weights.get(code, 10)
            weights.append(weight)
        
        rng = random.Random(seed)
        return rng.choices(available_errors, weights=weights, k=1)[0]
    
    def generate_mock_success_data(self, tool_name: str) -> Any:
        """Generate realistic mock data for success response."""
        if tool_name not in self.endpoints:
            return {"message": "Success"}
        
        endpoint = self.endpoints[tool_name]
        method = endpoint['method']
        
        if method == 'GET':
            if 'find' in tool_name.lower() or 'list' in tool_name.lower():
                return [
                    {"id": i, "name": f"Item-{i}", "status": "active"}
                    for i in range(1, self.config.mock_list_size + 1)
                ]
            else:
                return {"id": 1, "name": "Item-1", "status": "active"}
        
        elif method in ['POST', 'PUT']:
            return {
                "id": random.randint(1000, 9999),
                "status": "success",
                "message": f"{method} operation completed"
            }
        
        elif method == 'DELETE':
            return {"status": "deleted", "message": "Resource deleted successfully"}
        
        return {"message": "Success"}
    
    def mock_success_response(self, tool_name: str, params: dict) -> dict:
        """Return mocked success response (HTTP 200)."""
        if not self.config.mock_success_enabled:
            return {
                "status_code": 200,
                "body": {"message": "Success mock disabled"},
                "error": None,
                "tool_name": tool_name,
                "chaos_injected": False,
            }
        
        body = self.generate_mock_success_data(tool_name)
        return {
            "status_code": 200,
            "body": body,
            "error": None,
            "tool_name": tool_name,
            "chaos_injected": False,
        }
    
    def mock_error_response(self, tool_name: str, error_code: str) -> dict:
        """Return mocked error response."""
        if tool_name not in self.chaos_strategies:
            return {
                "status_code": 404,
                "body": {
                    "code": "404",
                    "type": "error",
                    "message": f"Unknown operation: {tool_name}"
                },
                "error": "Unknown operation",
                "tool_name": tool_name,
                "chaos_injected": False,
            }
        
        strategy = self.chaos_strategies[tool_name].get(error_code)
        if not strategy:
            return {
                "status_code": 500,
                "body": {
                    "code": "500",
                    "type": "error",
                    "message": "Internal server error"
                },
                "error": "Internal error",
                "tool_name": tool_name,
                "chaos_injected": True,
            }
        
        return {
            "status_code": int(error_code),
            "body": {
                "code": error_code,
                "type": "error",
                "message": strategy['message']
            },
            "error": f"HTTP {error_code}",
            "tool_name": tool_name,
            "chaos_injected": True,
        }
    
    async def call(
        self,
        tool_name: str,
        params: Dict[str, Any],
        failure_rate: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Simulate API call with optional chaos injection.
        
        Args:
            tool_name: Operation ID from OpenAPI spec
            params: Parameters for the API call
            failure_rate: Probability of error (0.0 to 1.0)
            seed: Random seed for determinism
        
        Returns:
            dict with statuscode, body, error, toolname, chaos_injected
        """
        if failure_rate is None:
            failure_rate = self.config.default_failure_rate
        if seed is None:
            seed = self.config.default_seed
        
        # ✅ USAR EL _should_inject_chaos() ARREGLADO
        inject_chaos = self._should_inject_chaos(failure_rate, seed)
        
        if not inject_chaos:
            return self.mock_success_response(tool_name, params)
        
        error_code = self.select_error_code(tool_name, seed)
        return self.mock_error_response(tool_name, error_code)
    
    def get_available_operations(self) -> List[str]:
        """Return list of all available operation IDs."""
        return list(self.endpoints.keys())
    
    def get_error_codes_for_operation(self, tool_name: str) -> List[str]:
        """Return list of error codes for a specific operation."""
        if tool_name not in self.chaos_strategies:
            return []
        return list(self.chaos_strategies[tool_name].keys())


async def test_chaos_agent():
    """Test ChaosAgent with Petstore API."""
    print("=" * 70)
    print("CHAOS AGENT v10 - Universal OpenAPI 3.0 Simulator")
    print("=" * 70)
    
    config = ChaosAgentConfig(
        openapi_spec_url="https://petstore3.swagger.io/v3/openapi.json",
        default_failure_rate=0.0,
        default_seed=42,
    )
    
    agent = ChaosAgent(config)
    
    print(f"\nAvailable operations: {len(agent.get_available_operations())}")
    print(f"Examples: {agent.get_available_operations()[:5]}")
    
    print("\nTEST 1: No chaos - findPetsByStatus")
    result1 = await agent.call(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=0.0,
        seed=42,
    )
    print(f"  Status: {result1['status_code']}, Chaos: {result1['chaos_injected']}")
    print(f"  Body: {str(result1['body'])[:100]}...")
    
    print("\nTEST 2: With chaos - findPetsByStatus (100% failure rate)")
    result2 = await agent.call(
        tool_name="findPetsByStatus",
        params={"status": "available"},
        failure_rate=1.0,
        seed=42,
    )
    print(f"  Status: {result2['status_code']}, Chaos: {result2['chaos_injected']}")
    print(f"  Error: {result2.get('error')}")
    print(f"  Body: {result2['body']}")
    
    print("\nTEST 3: With chaos - getPetById (different seed)")
    result3 = await agent.call(
        tool_name="getPetById",
        params={"petId": 1},
        failure_rate=1.0,
        seed=100,
    )
    print(f"  Status: {result3['status_code']}, Chaos: {result3['chaos_injected']}")
    print(f"  Error: {result3.get('error')}")
    print(f"  Body: {result3['body']}")
    
    print("\nTEST 4: Available error codes for operations")
    for op in ["findPetsByStatus", "getPetById", "placeOrder"]:
        codes = agent.get_error_codes_for_operation(op)
        print(f"  {op}: {codes}")
    
    print("=" * 70)
    print("CHAOS AGENT v10 TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    print("Testing ChaosAgent v10 (Universal)...")
    asyncio.run(test_chaos_agent())
