SiteRMAuth.setupAjaxAuth();
$(document).ready(function() {
    load_data();
    //setInterval(load_data, 300000);
});

function loadModel(modelID, sitename) {
    const formats = ["json-ld", "turtle", "ntriples"];
    const formatTitles = {
        "json-ld": "JSON-LD",
        turtle: "Turtle",
        ntriples: "N-Triples",
    };

    const model = $("<div></div>");
    const tabNav = $('<ul class="nav nav-tabs" role="tablist"></ul>');
    const tabContent = $('<div class="tab-content"></div>');
    let metadataSet = false;

    formats.forEach((fmt, index) => {
        $.ajax({
            url: `/api/${sitename}/models/${modelID}?rdfformat=${fmt}`,
            dataType: "json",
            async: false,
            error: function(xhr, status, error) {
                showAjaxWarning(
                    "Failed to load deltas",
                    `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
                );
                console.error("AJAX error:", status, xhr.responseText);
            },
            success: function(json) {
                if (!metadataSet) {
                    model.append(
                        `<div class="row"><b>Creation Time: </b>${json["creationTime"]}</div>`,
                    );
                    model.append(
                        `<div class="row"><b>Href: </b>${json["href"]}</div>`,
                    );
                    model.append(`<div class="row"><b>ID: </b>${json["id"]}</div>`);
                    model.append('<div class="row"><b>Full Model:</b></div>');
                    metadataSet = true;
                }

                const tabId = `${fmt}-${modelID}`;
                const isActive = index === 0 ? "active" : "";

                tabNav.append(`
                  <li class="nav-item">
                    <a class="nav-link ${isActive}" id="tab-${tabId}" data-toggle="tab" href="#${tabId}" role="tab">
                      ${formatTitles[fmt]}
                    </a>
                  </li>
                `);

                const tabPane = $(
                    `<div class="tab-pane fade ${isActive ? "show active" : ""}" id="${tabId}" role="tabpanel"></div>`,
                );
                mrmlSaver(json["model"], tabPane);
                tabContent.append(tabPane);
            },
        });
    });

    model.append(tabNav);
    model.append(tabContent);
    $("#v-pills-" + modelID)
        .empty()
        .append(model);

    $(`#v-pills-${modelID} [data-toggle="tab"]`).on("click", function(e) {
        e.preventDefault();
        $(this).tab("show");
    });
}

function defineAllModels(data, sitename) {
    menCol = $(
        '<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"><\/div>',
    );
    cntDiv = $('<div class="tab-content" id="v-pills-tabContent"><\/div>');
    latest = true;
    for (j = 0; j < data.length; j++) {
        if ($.isPlainObject(data[j])) {
            modID = data[j]["id"];
            tagName = modID;
            if (latest) {
                latest = false;
                tagName += " LATEST";
            }
            // add creationTime
            if (data[j]["creationTime"]) {
                tagName += " (" + data[j]["creationTime"] + ")";
            }

            menCol.append(
                '<a class="nav-link" id="v-pills-' +
                modID +
                '-tab" data-toggle="pill" onclick="loadModel(\'' +
                modID +
                "', '" +
                sitename +
                '\')" href="#v-pills-' +
                modID +
                '" role="tab" aria-controls="v-pills-' +
                modID +
                '" aria-selected="true">' +
                tagName +
                "<\/a>",
            );
            cntDiv.append(
                '<div class="tab-pane fade" id="v-pills-' +
                modID +
                '" role="tabpanel" aria-labelledby="v-pills-' +
                modID +
                '-tab"><\/div>',
            );
        }
    }
    nRow = $('<div class="row">');
    menCol = $('<div class="col-3">').append(menCol);
    cntDiv = $('<div class="col-9">').append(cntDiv);
    nRow.append(menCol).append(cntDiv);
    $("#view_fe_" + sitename).append(nRow);
}

function load_data() {
    var configdata = fetchConfig();
    defineSites(configdata, false);
    var sitename = configdata["general"]["sitename"];
    $.ajax({
        url: "/api/" + sitename + "/models?limit=100",
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
        success: function(json) {
            defineAllModels(json, sitename);
        },
    });
}