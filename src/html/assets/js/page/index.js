SiteRMAuth.setupAjaxAuth();
var configdata = fetchConfig();
var sitename = configdata ? configdata["general"]["sitename"] : null;
var archifyRequest = null;
var archifyTimer = null;

// Fill the switch/server filters; runs synchronously so multiselect.js sees the options on window load.
function loadFilters() {
    $.ajax({
        url: "/api/" + sitename + "/topo/gettopology",
        dataType: "json",
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load topology",
                escapeHtml(`HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`)
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            Object.keys(json).sort().forEach(function(name) {
                var devtype = (json[name]["DeviceInfo"] || {})["type"];
                $("#filter" + devtype).append(
                    $("<option>", {
                        value: name,
                        text: name,
                    }),
                );
            });
        },
    });
}

// Render the Archify diagram server side and show it in the sandboxed iframe (no same-origin access to the JWT).
function loadArchify() {
    if (archifyRequest) {
        archifyRequest.abort();
    }
    $("#topo-status").text("Rendering topology...");
    archifyRequest = $.ajax({
        url: "/api/" + sitename + "/topo/archify",
        data: {
            switch: $("#filterswitch").val() || [],
            server: $("#filterserver").val() || [],
        },
        traditional: true,
        dataType: "text",
        error: function(xhr, status, error) {
            if (status === "abort") {
                return;
            }
            $("#topo-status").text("");
            showAjaxWarning(
                "Failed to render topology",
                escapeHtml(`HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`)
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(html) {
            var frame = document.getElementById("topo");
            $("#topo-status").text("Loading diagram...");
            frame.onload = function() {
                $("#topo-status").text("");
            };
            frame.srcdoc = html;
        },
    });
}

function scheduleArchifyLoad() {
    clearTimeout(archifyTimer);
    archifyTimer = setTimeout(loadArchify, 400);
}

if (sitename) {
    loadFilters();
    $(document).ready(loadArchify);
}
