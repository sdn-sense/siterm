SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

function load_data() {
    const configdata = fetchConfig();
    const sitename = configdata["general"]["sitename"];

    $.ajax({
        url: "/api/" + sitename + "/monitoring/prometheus/metrics",
        dataType: "text",          // <-- this is the key change
        async: true,               // don't block the browser
        error: function (xhr, status, error) {
            showAjaxWarning(
                "Failed to load Prometheus metrics",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function (text) {
            const prometheusOutput = $("<div></div>");

            // Prometheus format is line-based
            text.split("\n").forEach(line => {
                if (!line.trim()) return;

                // Comments start with #
                if (line.startsWith("#")) {
                    prometheusOutput.append(
                        `<div class="text-muted small">${escapeHtml(line)}</div>`
                    );
                } else {
                    prometheusOutput.append(
                        `<div><code>${escapeHtml(line)}</code></div>`
                    );
                }
            });

            $("#prometheus-metrics").empty().append(prometheusOutput);
        }
    });
}