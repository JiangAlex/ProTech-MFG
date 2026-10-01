"""mfg — standalone manufacturing (MFG) test package.

Self-contained: depends only on pyyaml, tftpy, pexpect, and (optionally) pyftdi.
No coupling to any ATLAS core/ shim, Spirent, or other test modules.

Public API:
    from mfg.manufacturing_script import ManufacturingScript
    from mfg.console import Console
    from mfg.power_controller import PowerController
"""
