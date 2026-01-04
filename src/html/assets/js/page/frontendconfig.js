SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

function deletehost(hostname) {
    const docObj = document.getElementById("del-" + hostname);
    const params = {};

    for (let i = 0; i < docObj.elements.length; i++) {
        const fieldName = docObj.elements[i].name;
        const fieldValue = docObj.elements[i].value;
        if (fieldName) {
            params[fieldName] = fieldValue;
        }
    }

    const sitename = params["sitename"];
    const url = "/api/" + sitename + "/hosts";

    $.ajax({
        url: url,
        type: "DELETE",
        contentType: "application/json",
        data: JSON.stringify(params),
        success: function(result) {
            params["type"] = hostname.replace(/\./g, "_");
            newAlert("Host delete sent: " + JSON.stringify(result), params);
        },
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
    });
}

function reloadconfig(hostname) {
    const docObj = document.getElementById("rel-" + hostname);
    const params = {};
    for (let i = 0; i < docObj.elements.length; i++) {
        const fieldName = docObj.elements[i].name;
        const fieldValue = docObj.elements[i].value;
        if (fieldName) {
            params[fieldName] = fieldValue;
        }
    }
    fetch("/api/" + params["sitename"] + "/serviceaction", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(params),
        })
        .then((response) => response.json())
        .then((result) => {
            params["type"] = hostname.replace(/\./g, "_");
            newAlert(
                "Service action submitted:" + JSON.stringify(result),
                params,
            );
        });
}

function load_data() {
    var configdata = fetchConfig();
    var sitename = configdata["general"]["sitename"];
    defineSites(configdata);
    defineSitesConfig(configdata, sitename);
    $.ajax({
        url: "/api/" + sitename + "/hosts?details=true&limit=100",
        dataType: "json",
        data: {},
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(dataout) {
            for (j = 0; j < dataout.length; j++) {
                defineDTNConfig(dataout[j], sitename, dataout[j]["hostname"]);
            }
        },
    });
}