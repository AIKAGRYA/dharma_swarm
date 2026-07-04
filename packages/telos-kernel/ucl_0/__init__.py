"""UCL-0 finite evidence calculus kernel.

The P0 kernel checks finite receipt derivations and does not run object
programs. Object logics attach by adequacy in the LF sense described by
[Harper, Honsell, and Plotkin 1993](https://doi.org/10.1145/138027.138060).
"""

from ucl_0.receipt.identity import receipt_id, receipt_id_uri
from ucl_0.receipt.lfp import least_fixed_point, phi_step
from ucl_0.receipt.types import EvidenceRecord, Receipt, ValidityRecord, parse_receipt

__all__ = [
    "EvidenceRecord",
    "Receipt",
    "ValidityRecord",
    "least_fixed_point",
    "parse_receipt",
    "phi_step",
    "receipt_id",
    "receipt_id_uri",
]
