from datetime import datetime, timezone
import json
import math
from typing import List, Dict, Optional, Any, Union


class ClaimStatus:
    PENDING = "pending"
    VERIFIED = "verified"
    ENFORCED = "enforced"


class ClaimInputWorkType:
    TEXT = "text"
    IMAGE = "image"
    CODE = "code"
    MUSIC = "music"
    VIDEO = "video"
    DATA = "data"
    OTHER = "other"


class AuditEntryAction:
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    ENFORCED = "enforced"
    APPEALED = "appealed"
    ARWEAVE_ANCHORED = "arweave_anchored"


class FibonacciCadence:
    """
    Implements the core dynamic scale logic for adjusting intellectual debt periods and multipliers.
    Using standard Fibonacci sequence calculations to penalize delayed settlement/unauthorized absorption.
    """
    def __init__(self, current_period: int = 1):
        self.current_period = max(1, current_period)
        self.sequence = self._generate_sequence(self.current_period + 3)
        self.current_multiplier = self._get_multiplier_for_period(self.current_period)

    @staticmethod
    def _generate_sequence(n: int) -> List[int]:
        """Generates standard Fibonacci sequence list up to n elements."""
        if n <= 0:
            return []
        if n == 1:
            return [1]
        seq = [1, 1]
        while len(seq) < n:
            seq.append(seq[-1] + seq[-2])
        return seq

    def _get_multiplier_for_period(self, period: int) -> int:
        """Returns the Fibonacci multiplier associated with the given period index."""
        # Index offset to map period 1 to multiplier 1, period 2 to multiplier 2, etc.
        seq = self._generate_sequence(period + 1)
        return seq[-1] if seq else 1

    def calculate_adjusted_debt(self, base_debt: float) -> float:
        """Applies current period's multiplier to the base debt value."""
        return float(base_debt * self.current_multiplier)

    def advance_period(self) -> int:
        """Steps forward to the next Fibonacci cadence period."""
        self.current_period += 1
        self.sequence = self._generate_sequence(self.current_period + 3)
        self.current_multiplier = self._get_multiplier_for_period(self.current_period)
        return self.current_period

    def to_dict(self) -> Dict[str, Any]:
        """Serializes current cadence status to match TypeScript FibonacciCadence interface."""
        now = datetime.now(timezone.utc)
        return {
            "currentPeriod": self.current_period,
            "currentMultiplier": self.current_multiplier,
            "sequence": self.sequence,
            "periodStartDate": now.isoformat(),
            "nextPeriodDate": (now.replace(day=now.day + 1 if now.day < 28 else 1)).isoformat(), # Mock next execution cycle
            "description": f"Sovereign IP Enforcement Period {self.current_period}. Multiplier: x{self.current_multiplier}."
        }


class AuditEntry:
    """Represents a transaction entry within the decentralized audit ledger."""
    def __init__(
        self,
        entry_id: int,
        claim_id: int,
        action: str,
        entry_hash: str,
        arweave_tx_id: Optional[str] = None,
        notes: Optional[str] = None,
        created_at: Optional[str] = None
    ):
        self.id = entry_id
        self.claim_id = claim_id
        self.action = action if action in vars(AuditEntryAction).values() else AuditEntryAction.SUBMITTED
        self.entry_hash = entry_hash
        self.arweave_tx_id = arweave_tx_id
        self.notes = notes
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "claimId": self.claim_id,
            "action": self.action,
            "entryHash": self.entry_hash,
            "arweaveTxId": self.arweave_tx_id,
            "notes": self.notes,
            "createdAt": self.created_at
        }


class Claim:
    """Represents an active Intellectual Property sovereign claim within CRAprotocol."""
    def __init__(
        self,
        claim_id: int,
        creator: str,
        work_description: str,
        work_type: str,
        absorbed_by: str,
        date_absorbed: str,
        debt_value: float,
        arweave_tx_id: Optional[str] = None,
        evidence_url: Optional[str] = None,
        status: str = ClaimStatus.PENDING,
        fibonacci_period: int = 1,
        created_at: Optional[str] = None
    ):
        self.id = claim_id
        self.creator = creator
        self.work_description = work_description
        self.work_type = work_type if work_type in vars(ClaimInputWorkType).values() else ClaimInputWorkType.OTHER
        self.absorbed_by = absorbed_by
        self.date_absorbed = date_absorbed
        self.debt_value = float(debt_value)
        self.arweave_tx_id = arweave_tx_id
        self.evidence_url = evidence_url
        self.status = status if status in vars(ClaimStatus).values() else ClaimStatus.PENDING
        
        # Fibonacci Period tracking
        self.cadence = FibonacciCadence(current_period=fibonacci_period)
        self.fibonacci_period = self.cadence.current_period
        self.fibonacci_multiplier = self.cadence.current_multiplier
        self.adjusted_debt = self.cadence.calculate_adjusted_debt(self.debt_value)
        
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.audit_entries: List[AuditEntry] = []

    def update_status(self, new_status: str, arweave_tx_id: Optional[str] = None, notes: Optional[str] = None) -> AuditEntry:
        """Transition state machine safely while spawning an accompanying cryptographic Audit Entry."""
        if new_status in vars(ClaimStatus).values():
            self.status = new_status
        if arweave_tx_id:
            self.arweave_tx_id = arweave_tx_id

        # Generate structural entry hash matching decentralized framework verification specifications
        raw_hash_source = f"{self.id}-{self.status}-{arweave_tx_id or 'none'}-{datetime.now(timezone.utc).timestamp()}"
        entry_hash = f"cra_hash_{math.hash(raw_hash_source) & 0xffffffff:08x}"

        # Map state status to corresponding audit actions
        action_map = {
            ClaimStatus.PENDING: AuditEntryAction.SUBMITTED,
            ClaimStatus.VERIFIED: AuditEntryAction.VERIFIED,
            ClaimStatus.ENFORCED: AuditEntryAction.ENFORCED
        }
        action = action_map.get(self.status, AuditEntryAction.SUBMITTED)

        new_entry = AuditEntry(
            entry_id=len(self.audit_entries) + 1,
            claim_id=self.id,
            action=action,
            entry_hash=entry_hash,
            arweave_tx_id=arweave_tx_id,
            notes=notes
        )
        self.audit_entries.append(new_entry)
        return new_entry

    def apply_cadence_progression(self) -> None:
        """Tick claim cadence timeline up, recalculating dynamic IP debt leverage."""
        self.fibonacci_period = self.cadence.advance_period()
        self.fibonacci_multiplier = self.cadence.current_multiplier
        self.adjusted_debt = self.cadence.calculate_adjusted_debt(self.debt_value)

    def to_dict(self, include_audit: bool = True) -> Dict[str, Any]:
        """Outputs schema identical to TypeScript Orval definition (Claim / ClaimDetail)."""
        data = {
            "id": self.id,
            "creator": self.creator,
            "workDescription": self.work_description,
            "workType": self.work_type,
            "absorbedBy": self.absorbed_by,
            "dateAbsorbed": self.date_absorbed,
            "debtValue": self.debt_value,
            "arweaveTxId": self.arweave_tx_id,
            "evidenceUrl": self.evidence_url,
            "status": self.status,
            "fibonacciPeriod": self.fibonacci_period,
            "fibonacciMultiplier": self.fibonacci_multiplier,
            "adjustedDebt": self.adjusted_debt,
            "createdAt": self.created_at
        }
        if include_audit:
            data["auditEntries"] = [entry.to_dict() for entry in self.audit_entries]
        return data


class SovereignProtocolManager:
    """Manages collection-wide state, statistical calculations, and telemetry report compilation."""
    def __init__(self):
        self.claims: Dict[int, Claim] = {}
        self.global_cadence = FibonacciCadence()

    def create_claim(self, claim_input: Dict[str, Any]) -> Claim:
        """Factory pattern: Accept payload parameters, instantiate validated Sovereign Claim."""
        next_id = max(self.claims.keys(), default=0) + 1
        new_claim = Claim(
            claim_id=next_id,
            creator=claim_input["creator"],
            work_description=claim_input["workDescription"],
            work_type=claim_input["workType"],
            absorbed_by=claim_input["absorbedBy"],
            date_absorbed=claim_input["dateAbsorbed"],
            debt_value=claim_input["debtValue"],
            evidence_url=claim_input.get("evidenceUrl"),
            fibonacci_period=self.global_cadence.current_period
        )
        # Log submission event
        new_claim.update_status(ClaimStatus.PENDING, notes="Sovereign Claim registered into active local context.")
        self.claims[next_id] = new_claim
        return new_claim

    def get_protocol_stats(self) -> Dict[str, Any]:
        """Performs analytical aggregation over local claims, outputting dynamic statistics matching ProtocolStats specs."""
        total_claims = len(self.claims)
        total_debt = sum(c.debt_value for c in self.claims.values())
        total_adjusted = sum(c.adjusted_debt for c in self.claims.values())

        # Sub-metrics initialization
        by_status = {ClaimStatus.PENDING: 0, ClaimStatus.VERIFIED: 0, ClaimStatus.ENFORCED: 0}
        by_worktype = {k: 0 for k in vars(ClaimInputWorkType).values() if not k.startswith("__")}

        absorber_data: Dict[str, Dict[str, Any]] = {}
        recent_activity: List[Dict[str, Any]] = []

        for c in self.claims.values():
            # Update counters
            by_status[c.status] = by_status.get(c.status, 0) + 1
            by_worktype[c.work_type] = by_worktype.get(c.work_type, 0) + 1

            # Top Absorber Aggregates
            abs_system = c.absorbed_by
            if abs_system not in absorber_data:
                absorber_data[abs_system] = {
                    "system": abs_system,
                    "claimCount": 0,
                    "totalDebt": 0.0,
                    "totalAdjustedDebt": 0.0,
                    "verifiedCount": 0,
                    "enforcedCount": 0
                }
            
            node = absorber_data[abs_system]
            node["claimCount"] += 1
            node["totalDebt"] += c.debt_value
            node["totalAdjustedDebt"] += c.adjusted_debt
            if c.status == ClaimStatus.VERIFIED:
                node["verifiedCount"] += 1
            elif c.status == ClaimStatus.ENFORCED:
                node["enforcedCount"] += 1

            # Track audit logs for recent activity timeline
            for audit in c.audit_entries:
                recent_activity.append(audit.to_dict())

        # Sort recent entries by timestamp descending
        recent_activity.sort(key=lambda x: x["createdAt"], reverse=True)
        top_absorbers_list = sorted(absorber_data.values(), key=lambda x: x["totalAdjustedDebt"], reverse=True)

        return {
            "totalClaims": total_claims,
            "totalDebt": total_debt,
            "totalAdjustedDebt": total_adjusted,
            "claimsByStatus": by_status,
            "claimsByWorkType": by_worktype,
            "currentFibonacciPeriod": self.global_cadence.current_period,
            "currentFibonacciMultiplier": self.global_cadence.current_multiplier,
            "topAbsorbers": top_absorbers_list[:10], # Return top 10 systemic violators
            "recentActivity": recent_activity[:15]   # Return 15 latest sovereign actions
        }


# --- LOCAL SYSTEM PREFLIGHT TEST ---
if __name__ == '__main__':
    print("--- INITIATING SOVEREIGN IP PROTOCOL MANAGER TEST (CRAprotocol v0.1.0) ---")
    pm = SovereignProtocolManager()

    # Create Mock Claim Input conforming to OpenAPI requirements
    mock_claim_input = {
        "creator": "Sovereign Dev Group",
        "workDescription": "Optimized neural parser for decentralized state machines.",
        "workType": ClaimInputWorkType.CODE,
        "absorbedBy": "LargeScaleLLMCorp",
        "dateAbsorbed": datetime.now(timezone.utc).isoformat(),
        "debtValue": 25000.0,
        "evidenceUrl": "https://arweave.net/tx_evidence_id_123"
    }

    # Register Claim 1
    claim = pm.create_claim(mock_claim_input)
    print(f"[REGISTERED] Claim ID: {claim.id} | Base Debt: ${claim.debt_value} | Adjusted: ${claim.adjusted_debt}")

    # Advance global cadence period (increasing penalty multiplier scale)
    pm.global_cadence.advance_period() # Level 2 multiplier (2)
    pm.global_cadence.advance_period() # Level 3 multiplier (3)
    
    print(f"\n[CRITICAL CADENCE CHANGE] Escalating Global Cadence to Period: {pm.global_cadence.current_period}")
    claim.apply_cadence_progression()
    print(f"[RECALCULATED] Claim ID: {claim.id} | Multiplier: x{claim.fibonacci_multiplier} | New Adjusted Debt: ${claim.adjusted_debt}")

    # Process State Transition to Verified with Arweave TX Anchor
    print("\n[RESOLVING STATE TRANSITION] Cryptographically Anchoring Claim...")
    claim.update_status(
        new_status=ClaimStatus.VERIFIED,
        arweave_tx_id="ar_tx_90123_verification_proof",
        notes="Validated by local consensus engines. Proof published to Arweave."
    )

    # Output dynamic system telemetry stats
    stats = pm.get_protocol_stats()
    print("\n--- PROTOCOL RUNTIME SYSTEM TELEMETRY ---")
    print(json.dumps(stats, indent=2))