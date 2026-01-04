window.__layoutReady = false;

(async function() {
    async function loadTemplates() {
        const res = await fetch("/assets/templates/layout.html", {
            cache: "force-cache",
        });
        if (!res.ok) {
            throw new Error("Failed to load layout templates");
        }

        const html = await res.text();
        const container = document.createElement("div");
        container.innerHTML = html;

        // Register all templates globally
        container.querySelectorAll("template").forEach(tpl => {
            if (!document.getElementById(tpl.id)) {
                document.body.appendChild(tpl);
            }
        });
    }

    function mountTemplate(templateId, slotId) {
        const tpl = document.getElementById(templateId);
        const slot = document.getElementById(slotId);

        if (!tpl) {
            throw new Error(`Template not found: ${templateId}`);
        }
        if (!slot) {
            throw new Error(`Slot not found: ${slotId}`);
        }

        const node = tpl.content.cloneNode(true);
        slot.replaceWith(node);
    }

    // ---- bootstrap sequence ----
    await loadTemplates();

    mountTemplate("header-template", "header-slot");
    mountTemplate("sidebar-template", "sidebar-slot");
    window.__layoutReady = true;
})();

$(document).ready(async function() {
    SiteRMAuth.setupAjaxAuth();
    SiteRMAuth.setupGlobal401Handler();

    $("#loginBtn").on("click", async function() {
        try {
            await SiteRMAuth.login(
                $("#loginUser").val(),
                $("#loginPass").val()
            );
            window.location.reload();
        } catch (e) {
            console.log(e);
            SiteRMAuth.showLoginError(e.message);
        }
    });

    $("#logoutLink").on("click", function(e) {
        e.preventDefault();
        SiteRMAuth.logout();
    });

    await SiteRMAuth.checkSession();

    fetchStatus();
    setInterval(fetchStatus, 5000);
});

$("#myTab a").click(function(e) {
    e.preventDefault();
    $(this).tab("show");
});