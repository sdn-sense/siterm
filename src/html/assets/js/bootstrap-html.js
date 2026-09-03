window.__layoutReady = false;
window.__pendingShowLogin = false;

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

    // Auth plumbing must be armed before any page script fires its first
    // $.ajax (page load_data() runs on DOMContentLoaded, which on light pages
    // happens before the async template fetch below resolves).
    SiteRMAuth.setupAjaxAuth();
    SiteRMAuth.setupGlobal401Handler();

    // ---- bootstrap sequence ----
    try {
        await loadTemplates();
        mountTemplate("header-template", "header-slot");
        mountTemplate("sidebar-template", "sidebar-slot");
    } catch (e) {
        console.error(e);
    }
    window.__layoutReady = true;

    // The login overlay lives in header-template. Anything that asked for it
    // before the template was mounted (a 401 handler, a page script, the
    // session check below) set __pendingShowLogin instead of silently no-oping.
    if (window.__pendingShowLogin) {
        SiteRMAuth.showLogin();
    }

    // Runs after the overlay exists, so "no token" reliably shows the login
    // screen on every page - not just the heavier ones that happened to win
    // the race.
    await SiteRMAuth.checkSession();

    fetchStatus();
    setInterval(fetchStatus, 5000);
})();

// Delegated bindings: #loginBtn / #logoutLink / #myTab are injected from
// templates or built at runtime, so bind on document rather than the elements.
$(document).on("click", "#loginBtn", async function() {
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

$(document).on("click", "#logoutLink", function(e) {
    e.preventDefault();
    SiteRMAuth.logout();
});

$(document).on("click", "#myTab a", function(e) {
    e.preventDefault();
    $(this).tab("show");
});
