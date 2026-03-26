SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
});

// Function to prefill the site dropdown
function prefillSites() {
    var configdata = fetchConfig();
    const dropdown = document.getElementById("f0_sitename");
    sitename = configdata["general"]["sitename"];
    const opt = document.createElement("option");
    opt.value = sitename;
    opt.textContent = sitename;
    dropdown.appendChild(opt);
}

// Helper function to add options to a dropdown
function addDropDown(name, dropdown) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    dropdown.append(opt);
}

// Function to load active deltas and populate the instance dropdown
function loadModel(sitename) {
    $.ajax({
        url: "/api/" + sitename + "/frontend/activedeltas",
        dataType: "json",
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load active deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            const dropdown = document.getElementById("f0_instanceid");
            dropdown.innerHTML = '<option value="">Choose an instance</option>'; // Reset dropdown

            // Loop through each delta in the response
            Object.keys(json).forEach(function(key) {
                const delta = json[key];
                // Access vsw or rst if present
                ["vsw", "rst", "kube", "singleport"].forEach((type) => {
                    if (delta && delta[type]) {
                        // Loop through each key in vsw, rst, kube, or singleport
                        for (const key in delta[type]) {
                            if (delta[type].hasOwnProperty(key)) {
                                const opt = document.createElement("option");
                                opt.value = key; // The key is used as the value
                                opt.textContent = key; // The key is shown as the option text
                                dropdown.appendChild(opt);
                            }
                        }
                    }
                });
            });
        },
    });
}

function submitForm(formId) {
    const docObj = document.getElementById(formId);
    const params = {};

    for (let i = 0; i < docObj.elements.length; i++) {
        const fieldName = docObj.elements[i].name;
        const fieldValue = docObj.elements[i].value;

        if (fieldName) {
            if (fieldName === "starttimestamp" || fieldName === "endtimestamp") {
                const date = new Date(fieldValue);
                params[fieldName] = Math.floor(date.getTime() / 1000);
            } else {
                params[fieldName] = fieldValue;
            }
        }
    }

    $.ajax({
        url: "/api/" + params["sitename"] + "/setinstancestartend",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify(params),
        success: function(result) {
            params["type"] = "main";
            newAlert(
                "New change action request submitted: " + JSON.stringify(result),
                params
            );
        },
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to submit change action request",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
    });
}

function load_data() {
    prefillSites();
}