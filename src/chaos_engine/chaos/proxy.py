"""
Chaos Proxy - Middleware for Chaos Injection.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from chaos_engine.core.types import Status

_FALLBACK_ERROR_CODES: Dict[str, str] = {
    "500": "Internal Server Error (Fallback)",
    "503": "Service Unavailable (Fallback)",
}


class ChaosProxy:
    def __init__(
        self,
        failure_rate: float,
        seed: int,
        mock_mode: bool = False,
        verbose: bool = False,
        error_codes_path: str | Path | None = None,
    ):
        self.failure_rate = failure_rate
        self.rng = random.Random(seed)
        self.mock_mode = mock_mode
        self.verbose = verbose
        self.logger = logging.getLogger("ChaosProxy")
        self.base_url = "https://petstore3.swagger.io/api/v3"
        self.error_codes = self._load_error_codes(error_codes_path)
        self.base_delay = 1.0
        self._client: httpx.AsyncClient | None = None

    def _load_error_codes(self, explicit_path: str | Path | None) -> Dict[str, str]:
        """Load HTTP error definitions from knowledge base."""
        try:
            if explicit_path is not None:
                json_path = Path(explicit_path)
            else:
                # Default: derive from __file__ (works in source-layout installs)
                project_root = Path(__file__).resolve().parents[3]
                json_path = project_root / "assets" / "knowledge_base" / "http_error_codes.json"

            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)

            self.logger.warning("http_error_codes.json not found at %s. Using fallback.", json_path)
            return dict(_FALLBACK_ERROR_CODES)

        except Exception:
            self.logger.warning("Error loading http_error_codes.json", exc_info=True)
            return dict(_FALLBACK_ERROR_CODES)

    def calculate_jittered_backoff(self, seconds: float) -> float:
        """
        Calculates the wait time with Jitter (randomness).
        It uses the proxy's random number generator to maintain test determinism.
        """
        jitter_factor = 0.5  
        random_offset = self.rng.random() * seconds * jitter_factor
        
        # El backoff final es el tiempo base + el offset aleatorio.
        jittered_delay = seconds + random_offset
        return jittered_delay

    async def send_request(self, method: str, endpoint: str, params: dict = None, json_body: dict = None) -> Dict[str, Any]:
 
        # Zero-Trust: Basic schema validation
        if json_body and not isinstance(json_body.get('id'), int) and 'id' in json_body:
             self.logger.error("❌ SECURITY: Invalid schema detected (ID is not an integer).")
             return {"status": Status.ERROR, "code": 400, "message": "Input validation failed: ID must be integer."}

        # 1. Chaos Check
        if self.rng.random() < self.failure_rate:
            keys = list(self.error_codes.keys())
            if not keys: keys = ["500"]
            
            error_code = self.rng.choice(keys)
            error_msg = self.error_codes.get(error_code, "Unknown Error")
            
            self.logger.info("CHAOS INJECTED: Simulating %s on %s", error_code, endpoint)
            return {"status": Status.ERROR, "code": int(error_code), "message": f"Simulated Chaos: {error_msg}"}

        # 2. Mock Mode
        if self.mock_mode:
            self.logger.info("MOCK API CALL: %s %s (Skipping network)", method, endpoint)
            return self._generate_mock_response(method, endpoint)
        
        # 3. Real API Call
        self.logger.info("REAL API CALL: %s %s", method, endpoint)
        url = f"{self.base_url}{endpoint}"
        client = await self._get_client()
        try:
            if method == "GET":
                resp = await client.get(url, params=params, timeout=10.0)
            elif method == "POST":
                resp = await client.post(url, json=json_body, timeout=10.0)
            elif method == "PUT":
                resp = await client.put(url, json=json_body, timeout=10.0)
            elif method == "DELETE":
                resp = await client.delete(url, timeout=10.0)
            elif method == "PATCH":
                resp = await client.patch(url, json=json_body, timeout=10.0)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code >= 400:
                self.logger.warning("API Error %d: %s", resp.status_code, resp.text[:100])
                return {"status": Status.ERROR, "code": resp.status_code, "message": resp.text}

            return {"status": Status.SUCCESS, "code": resp.status_code, "data": resp.json()}

        except Exception as e:
            self.logger.error("Network Exception: %s", e)
            return {"status": Status.ERROR, "code": 500, "message": str(e)}

    async def _get_client(self) -> httpx.AsyncClient:
        """Return reusable httpx client, creating one if needed."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        """Close the reusable HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _generate_mock_response(self, method: str, endpoint: str) -> Dict[str, Any]:
        if "inventory" in endpoint:
            return {"status": Status.SUCCESS, "code": 200, "data": {"available": 100, "sold": 5, "pending": 2}}
        elif "findByStatus" in endpoint:
            return {"status": Status.SUCCESS, "code": 200, "data": [{"id": 12345, "name": "MockPet", "status": "available"}]}
        elif "order" in endpoint:
            return {"status": Status.SUCCESS, "code": 200, "data": {"id": 999, "petId": 12345, "status": "placed", "complete": True}}
        elif "pet" in endpoint and method == "PUT":
             return {"status": Status.SUCCESS, "code": 200, "data": {"id": 12345, "name": "MockPet", "status": "sold"}}
        else:
            return {"status": Status.SUCCESS, "code": 200, "data": {"message": "Mock success"}}