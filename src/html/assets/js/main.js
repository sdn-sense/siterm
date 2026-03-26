(function(window, $) {
    "use strict";

    const TOKEN_KEY = "siterm_access_token";

    function getToken() {
        return localStorage.getItem(TOKEN_KEY);
    }

    function setToken(tok) {
        localStorage.setItem(TOKEN_KEY, tok);
    }

    function clearToken() {
        localStorage.removeItem(TOKEN_KEY);
    }

    function showLogin() {
        $("#loginOverlay").show();
    }

    function hideLogin() {
        $("#loginOverlay").hide();
    }

    function showLoginError(msg) {
        $("#loginError").removeClass("d-none").text(msg || "");
    }

    function setupAjaxAuth() {
        $.ajaxSetup({
            beforeSend: function(xhr) {
                const tok = getToken();
                if (tok) {
                    xhr.setRequestHeader("Authorization", "Bearer " + tok);
                }
            }
        });
    }

    async function authFetch(url, opts = {}) {
        opts.headers = opts.headers || {};
        const tok = getToken();
        if (tok) {
            opts.headers["Authorization"] = "Bearer " + tok;
        }
        return fetch(url, opts);
    }

    async function login(username, password) {
        showLoginError("");
        const res = await fetch("/auth/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                username,
                password
            })
        });

        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(body.detail || body.message || "Login failed");
        }

        setToken(body.access_token);
        setupAjaxAuth();
        hideLogin();
    }

    function logout() {
        clearToken();
        showLogin();
    }

    async function checkSession() {
        const tok = getToken();
        if (!tok) {
            showLogin();
            return false;
        }

        try {
            const res = await authFetch("/auth/whoami");
            if (!res.ok) {
                logout();
                return false;
            }
            return true;
        } catch {
            logout();
            return false;
        }
    }

    async function whoami() {
        try {
            const res = await authFetch("/auth/whoami");
            if (!res.ok) {
                logout();
                return null;
            }
            return await res.json();
        } catch {
            logout();
            return null;
        }
    }

    function setupGlobal401Handler() {
        $(document).ajaxError(function(_evt, jqxhr) {
            if (jqxhr && jqxhr.status === 401) {
                showLoginError("Session expired. Please login again.");
                logout();
            }
        });
    }

    window.SiteRMAuth = {
        login,
        logout,
        checkSession,
        whoami,
        authFetch,
        setupAjaxAuth,
        setupGlobal401Handler,
        showLogin,
        hideLogin,
        showLoginError
    };
})(window, jQuery);

function showAjaxWarning(message, details) {
    const alert = $(`
        <div class="alert alert-warning alert-dismissible fade show" role="alert">
            <strong>Warning:</strong> ${message}
            ${details ? `<div class="small text-muted mt-1">${details}</div>` : ""}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        </div>
    `);

    $("#maindiv").prepend(alert);
}


var entityMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
    "/": "&#x2F;",
    "`": "&#x60;",
    "=": "&#x3D;",
};

function newAlert(alertMessage, params, alertType = "alert-success") {
    alert = $(
        '<div class="alert ' +
        alertType +
        ' alert-dismissible fade show" role="alert"><\/div>',
    );
    alert.append(alertMessage);
    alert.append(
        '<button type="button" class="close" data-dismiss="alert" aria-label="Close">',
    );
    $("#alerts" + params["type"]).append(alert);
}

function escapeHtml(string) {
    return String(string).replace(/[&<>"'`=\/]/g, function(s) {
        return entityMap[s];
    });
}

function mrmlSaver(dataIn, saveObj) {
    modCod = $("<code></code>");
    preCod = $("<pre></pre>");
    splData = dataIn.split("\n");
    for (var line in splData) {
        preCod.append(
            '<div class="row model-row">' + escapeHtml(splData[line]) + "</div>",
        );
    }
    modCod.append(preCod);
    saveObj.append(modCod);
}

function defineSites(data, definehosts = true) {
    sitesTab = $('<ul class="nav nav-pills" id="myTab" role="tablist"></ul>');
    allSites = $('<div id="sites" class="tab-content"></div>');
    sitename = data["general"]["sitename"];
    nName = sitename;
    // FE Config
    sitesTab.append(
        '<li class="nav-item" role="presentation"><a class="nav-link" data-toggle="tab" aria-controls="' +
        nName +
        '" aria-selected="false" id="tab_fe_' +
        nName +
        '"  href="#view_fe_' +
        nName +
        '">' +
        nName +
        " FE</a></li>",
    );
    allSites.append(
        '<div class="tab-pane fade" role="tabpanel" aria-labelledby="tab_fe_' +
        nName +
        '" id="view_fe_' +
        nName +
        '"></div>',
    );
    // All DTNs
    if (definehosts) {
        $.ajax({
            url: "/api/" + sitename + "/hosts?details=false&limit=100",
            dataType: "json",
            async: false,
            error: function (xhr, status, error) {
                showAjaxWarning(
                    "Failed to load hosts",
                    `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
                );
                console.error("AJAX error:", status, xhr.responseText);
            },
            success: function (json) {
                for (let j = 0; j < json.length; j++) {
                    const hostname = json[j]["hostname"];
                    const htmlhostname = hostname.replace(/\./g, "_");
                    const nName = sitename + "_" + htmlhostname;

                    // --- tab ---
                    const tab = $(
                        `<li class="nav-item" role="presentation">
                            <a class="nav-link"
                            data-toggle="tab"
                            aria-controls="${nName}"
                            aria-selected="false"
                            id="tab_${nName}"
                            href="#view_${nName}"
                            data-hostname="${hostname}"
                            data-loaded="false">
                            ${hostname}
                            </a>
                        </li>`
                    );

                    sitesTab.append(tab);

                    // --- content pane ---
                    allSites.append(
                        `<div class="tab-pane fade row"
                            role="tabpanel"
                            aria-labelledby="tab_${nName}"
                            id="view_${nName}">
                        </div>`
                    );

                    tab.find("a").one("shown.bs.tab", function () {
                        const $link = $(this);
                        const host = $link.data("hostname");
                        const target = $("#view_" + nName);

                        $.ajax({url: "/api/" + sitename + "/hosts?details=true&limit=1&hostname=" +encodeURIComponent(host),
                            dataType: "json",
                            success: function (dataout) {
                                if (!dataout || !dataout.length) {
                                    target.html(
                                        '<div class="col-12 text-warning">No data returned</div>'
                                    );
                                    return;
                                }

                                defineDTNConfig(
                                    dataout[0],
                                    sitename,
                                    dataout[0]["hostname"]
                                );
                            },
                            error: function (xhr, status, error) {
                                showAjaxWarning(
                                    "Failed to load host details",
                                    `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
                                );
                                target.html(
                                    '<div class="col-12 text-danger">Failed to load host details</div>'
                                );
                            },
                        });
                    });
                }
            },
        });
    }
    $("#sites_tab").append(sitesTab);
    $("#main_tab").append(allSites);
}

function dumpData(data, configLine) {
    if (Array.isArray(data)) {
        for (i = 0; i < data.length; i++) {
            dumpData(data[i], configLine);
        }
    } else if ($.isPlainObject(data)) {
        for (var key in data) {
            configLine.append("<b>" + key + ":</b>  ");
            dumpData(data[key], configLine);
            configLine.append("</br>");
        }
    } else {
        configLine.append(data + " ");
    }
}

function defineHostButtons(data, sitename, hostname) {
    htmlhostname = hostname.replace(/\./g, "_");
    controlRow = $('<div class="row">');
    // Add Remove button for all, except default
    if (hostname != "default") {
        controlRow.append(
            '<div class="px-1 py-1"><form onsubmit="deletehost(\'' +
            htmlhostname +
            '\');return false" id="del-' +
            htmlhostname +
            '" name="del-' +
            htmlhostname +
            '"><input id="host-' +
            htmlhostname +
            '" name="hostname" type="hidden" value="' +
            hostname +
            '"><input id="ip-' +
            htmlhostname +
            '" name="ip" type="hidden" value="' +
            data["ip"] +
            '"><input id="sitename-' +
            htmlhostname +
            '" name="sitename" type="hidden" value="' +
            sitename +
            '"><input value="Delete Host" type="submit" class="btn btn-danger"></form></div>',
        );
    }
    // Add Reload Config button
    controlRow.append(
        '<div class="px-1 py-1"><form onsubmit="reloadconfig(\'' +
        htmlhostname +
        '\');return false" id="rel-' +
        htmlhostname +
        '" name="rel-' +
        htmlhostname +
        '"><input id="host-' +
        htmlhostname +
        '" name="hostname" type="hidden" value="' +
        hostname +
        '"><input id="servicename-' +
        htmlhostname +
        '" name="servicename" type="hidden" value="ALL"><input id="action-' +
        htmlhostname +
        '" name="action" type="hidden" value="reload"><input id="sitename-' +
        htmlhostname +
        '" name="sitename" type="hidden" value="' +
        sitename +
        '"><input value="Reload Config" type="submit" class="btn btn-info"></form></div>',
    );
    return controlRow;
}

function defineDTNConfig(data, sitename, hostname) {
    htmlhostname = hostname.replace(/\./g, "_");
    menCol = $('<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"></div>');
    cntDiv = $('<div class="tab-content" id="v-pills-tabContent"></div>');
    for (var key in data["hostinfo"]) {
        if (key === "Summary") {
            continue;
        }
        if ($.isPlainObject(data["hostinfo"][key])) {
            menCol.append(
                '<a class="nav-link" id="v-pills-' +
                htmlhostname +
                "_" +
                key +
                '-tab" data-toggle="pill" href="#v-pills-' +
                htmlhostname +
                "_" +
                key +
                '" role="tab" aria-controls="v-pills-' +
                htmlhostname +
                "_" +
                key +
                '" aria-selected="true">' +
                key +
                "</a>",
            );
            cntDiv.append(
                '<div class="tab-pane fade" id="v-pills-' +
                htmlhostname +
                "_" +
                key +
                '" role="tabpanel" aria-labelledby="v-pills-' +
                htmlhostname +
                "_" +
                key +
                '-tab"></div>',
            );
        }
    }
    buttons = defineHostButtons(data, sitename, hostname);
    nRow = $('<div class="row">');
    menCol = $('<div class="col-3">').append(menCol);
    cntDiv = $('<div class="col-9">').append(cntDiv);
    nRow.append(menCol).append(cntDiv);
    $("#view_" + sitename + "_" + htmlhostname)
        .append('<div class="col-md-12" id="alerts' + htmlhostname + '"></div>')
        .append(buttons)
        .append(nRow);

    for (var key in data["hostinfo"]) {
        sitesConfig = $(
            '<table id="agent_' +
            htmlhostname +
            "_" +
            key +
            '" class="table"></table>',
        );
        sitesConfig.append(
            '<thead class="thead-dark"><tr><th scope="col">Parameter</th><th scope="col">Value</th></tr></thead>',
        );
        for (var key1 in data["hostinfo"][key]) {
            line = $("<tr></tr>");
            configLine = $("<td></td>");
            line.append('<th scope="row">' + key1 + "</th>");
            dumpData(data["hostinfo"][key][key1], configLine);
            line.append(configLine);
            sitesConfig.append(line);
        }
        $("#v-pills-" + htmlhostname + "_" + key).append(sitesConfig);
    }
}

function defineSitesConfig(data, sitename) {
    sitesConfig = $('<table id="viewtb_' + sitename + '" class="table"></table>');
    sitesConfig.append(
        '<thead class="thead-dark"><tr><th scope="col">Parameter</th><th scope="col">Value</th></tr></thead>',
    );
    for (var key in data) {
        if (key == "hostinfo") {
            continue;
        }
        line = $("<tr></tr>");
        line.append('<th scope="row">' + key + "</th>");
        configLine = $("<td></td>");
        dumpData(data[key], configLine);
        line.append(configLine);
        sitesConfig.append(line);
    }
    buttons = defineHostButtons(data, sitename, "default");
    $("#view_fe_" + sitename)
        .append(buttons)
        .append(sitesConfig);
}

function doSiteUpdate(ids) {
    strSite = document.getElementById(ids + "sitename").value;
    $.ajax({
        url: "/api/frontend/gethosts",
        dataType: "json",
        data: "",
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            for (j = 0; j < json.length; j++) {
                addDropDown(json[j]["hostname"], $("#" + ids + "dtn"));
            }
        },
    });
}

function doDTNUpdate(ids) {
    strDTN = document.getElementById(ids + "dtn").value;
    strSite = document.getElementById(ids + "sitename").value;
    $.ajax({
        url: "/api/frontend/gethosts",
        dataType: "json",
        data: "",
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json) {
            for (j = 0; j < json.length; j++) {
                if (strDTN == json[j]["hostname"]) {
                    var myObject = (0, eval)("(" + json[j]["hostinfo"] + ")");
                    for (const [key, value] of Object.entries(
                            myObject["NetInfo"]["interfaces"],
                        )) {
                        if (!$.isEmptyObject(value["vlans"])) {
                            for (const [key1, value1] of Object.entries(value["vlans"])) {
                                if (value1["provisioned"]) {
                                    addDropDown(key1, $("#" + ids + "interface"));
                                }
                            }
                        }
                    }
                }
            }
        },
    });
}

function addDropDown(dropdownVal, saveObj) {
    saveObj.append("<option>" + dropdownVal + "</option>");
}

// Credit to: https://stackoverflow.com/questions/4810841/pretty-print-json-using-javascript
function syntaxHighlight(json) {
    json = json
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    return json.replace(
        /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
        function(match) {
            var cls = "number";
            if (/^"/.test(match)) {
                if (/:$/.test(match)) {
                    cls = "key";
                } else {
                    cls = "string";
                }
            } else if (/true|false/.test(match)) {
                cls = "boolean";
            } else if (/null/.test(match)) {
                cls = "null";
            }
            return '<span class="' + cls + '">' + match + "</span>";
        },
    );
}


async function fetchAndUpdate({
    url,
    elementId,
    label,
    okCheck,
    okValue = "OK",
    failValue = "FAIL",
}) {
    const okClass = "text-success mr-3";
    const failClass = "text-danger mr-3";
    const el = document.getElementById(elementId);

    try {
        const resp = await SiteRMAuth.authFetch(url);
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const data = await resp.json();
        const isOk = okCheck(data);

        const value = isOk ?
            (typeof okValue === "function" ? okValue(data) : okValue) :
            (typeof failValue === "function" ? failValue(data) : failValue);

        el.textContent = `${label}: ${value}`;
        el.className = isOk ? okClass : failClass;
    } catch (err) {
        console.error(`Error fetching ${label.toLowerCase()}:`, err);
        el.textContent = `${label}: ERROR`;
        el.className = failClass;
    }
}

function fetchConfig() {
    SiteRMAuth.setupAjaxAuth();
    var configdata = null;
    $.ajax({
        url: "/api/frontend/configuration",
        dataType: "json",
        async: false,
        error: function(xhr, status, error) {
            showAjaxWarning(
                "Failed to load deltas",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(response) {
            configdata = response;
        },
    });
    return configdata;
}

async function fetchStatus() {
    if (!window.__layoutReady) return;
    // Fire them independently; no shared failure modes
    fetchAndUpdate({
        url: "/api/alive",
        elementId: "alive-status",
        label: "Alive",
        okCheck: (d) => d.status === "alive",
        okValue: "ALIVE",
        failValue: (d) => d.status ?? "DEAD"
    });

    fetchAndUpdate({
        url: "/api/ready",
        elementId: "ready-status",
        label: "Ready",
        okCheck: (d) => d.status === "ready",
        okValue: "READY",
        failValue: (d) => d.status ?? "NOT READY"
    });

    fetchAndUpdate({
        url: "/api/liveness",
        elementId: "liveness-status",
        label: "Liveness",
        okCheck: (d) => d.status === "ok",
        okValue: "ALIVE",
        failValue: (d) => d.status ?? "DEAD"
    });

    fetchAndUpdate({
        url: "/api/readiness",
        elementId: "readiness-status",
        label: "Readiness",
        okCheck: (d) => d.status === "ok",
        okValue: "READY",
        failValue: (d) => d.status ?? "NOT READY"
    });

    fetchAndUpdate({
        url: "/auth/whoami",
        elementId: "whoami-status",
        label: "Whoami",
        okCheck: (d) => d.user !== undefined,
        okValue: (d) => d.user ?? "Unknown Username",
        failValue: "NOT LOGGED IN"
    });

}