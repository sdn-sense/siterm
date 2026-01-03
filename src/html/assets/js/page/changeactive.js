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
    docObj = document.getElementById(formId);
    var params = {};
    for (var i = 0; i < docObj.elements.length; i++) {
        var fieldName = docObj.elements[i].name;
        var fieldValue = docObj.elements[i].value;
        if (fieldName) {
            if (
                fieldName === "starttimestamp" ||
                fieldName === "endtimestamp"
            ) {
                var date = new Date(fieldValue);
                params[fieldName] = Math.floor(date.getTime() / 1000);
            } else {
                params[fieldName] = fieldValue;
            }
        }
    }

    fetch("/api/" + params["sitename"] + "/setinstancestartend", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(params),
        })
        .then((response) => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error(
                    `HTTP ${response.status}: ${response.statusText}`,
                );
            }
        })
        .then((result) => {
            params["type"] = "main";
            newAlert(
                "New change action request submitted: " + JSON.stringify(result),
                params,
            );
        })
        .catch((error) => {
            params["type"] = "main";
            newAlert("Error: " + error.message, params, "alert-danger");
        });
}

function load_data() {
    prefillSites();
}