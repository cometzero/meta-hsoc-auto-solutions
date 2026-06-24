#
# SPDX-License-Identifier: MIT
#

# This class is enabled by build.sh only on hosts where BitBake's worker
# network namespace setup is blocked after unshare() succeeds. Marking tasks as
# network-enabled prevents bitbake-worker from entering that broken path.
APOLLO_BITBAKE_DISABLE_NETWORK_SANDBOX ??= "0"

addhandler apollo_bitbake_network_sandbox_handler
apollo_bitbake_network_sandbox_handler[eventmask] = "bb.event.RecipeTaskPreProcess"
python apollo_bitbake_network_sandbox_handler() {
    if not bb.utils.to_boolean(d.getVar("APOLLO_BITBAKE_DISABLE_NETWORK_SANDBOX")):
        return

    for task in getattr(e, "tasklist", []):
        d.setVarFlag(task, "network", "1")
}
