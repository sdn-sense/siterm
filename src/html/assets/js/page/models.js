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
                    "Failed to load model " + modelID,
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

const MODELS_PAGE_SIZE = 50;

function defineAllModels(data, sitename, offset) {
    const menCol = $(
        '<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"><\/div>',
    );
    const cntDiv = $('<div class="tab-content" id="v-pills-tabContent"><\/div>');
    for (let j = 0; j < data.length; j++) {
        if ($.isPlainObject(data[j])) {
            const modID = data[j]["id"];
            let tagName = modID;
            // Models are returned newest first, so only the first entry of the first page is the latest.
            if (offset === 0 && j === 0) {
                tagName += " LATEST";
            }
            // add creationTime
            if (data[j]["creationTime"]) {
                tagName += " (" + data[j]["creationTime"] + ")";
            }

            menCol.append(
                $('<a class="nav-link" data-toggle="pill" role="tab" aria-selected="true"></a>')
                .attr("id", "v-pills-" + modID + "-tab")
                .attr("href", "#v-pills-" + modID)
                .attr("aria-controls", "v-pills-" + modID)
                .on("click", () => loadModel(modID, sitename))
                .text(tagName)
            );
            cntDiv.append(
                $('<div class="tab-pane fade" role="tabpanel"></div>')
                .attr("id", "v-pills-" + modID)
                .attr("aria-labelledby", "v-pills-" + modID + "-tab")
            );
        }
    }
    const nRow = $('<div class="row">')
        .append($('<div class="col-3">').append(menCol))
        .append($('<div class="col-9">').append(cntDiv));
    $("#models_list_" + sitename).empty().append(nRow);
}

function loadModelsPage(sitename, offset) {
    $.ajax({
        url: "/api/" + sitename + "/models",
        dataType: "json",
        data: {
            limit: MODELS_PAGE_SIZE,
            offset: offset
        },
        error: function(xhr, status, error) {
            if (xhr.status === 404) {
                $("#models_list_" + sitename).empty().append($('<div class="alert alert-info"></div>').text("No models found."));
                $("#models_pager_top_" + sitename + ", #models_pager_bottom_" + sitename).empty();
                return;
            }
            showAjaxWarning(
                "Failed to load list of models",
                `HTTP ${xhr.status} – ${error} - xhr: ${xhr.responseText}`
            );
            console.error("AJAX error:", status, xhr.responseText);
        },
        success: function(json, status, xhr) {
            const total = totalCountHeader(xhr);
            const onPage = (newOffset) => loadModelsPage(sitename, newOffset);
            defineAllModels(json, sitename, offset);
            $("#models_pager_top_" + sitename).empty().append(paginationNav(offset, MODELS_PAGE_SIZE, json.length, total, onPage));
            $("#models_pager_bottom_" + sitename).empty().append(paginationNav(offset, MODELS_PAGE_SIZE, json.length, total, onPage));
        },
    });
}

function load_data() {
    var configdata = fetchConfig();
    if (!configdata) {
        return;
    }
    defineSites(configdata, false);
    var sitename = configdata["general"]["sitename"];
    $("#view_fe_" + sitename).append(
        $("<div></div>").attr("id", "models_pager_top_" + sitename),
        $("<div></div>").attr("id", "models_list_" + sitename),
        $("<div></div>").attr("id", "models_pager_bottom_" + sitename),
    );
    loadModelsPage(sitename, 0);
}