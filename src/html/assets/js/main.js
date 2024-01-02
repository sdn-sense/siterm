var entityMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
  '/': '&#x2F;',
  '`': '&#x60;',
  '=': '&#x3D;',
};

function escapeHtml (string) {
  return String(string).replace(/[&<>"'`=\/]/g, function (s) {
    return entityMap[s];
  });
}

      function mrmlSaver(dataIn, saveObj) {
          modCod = $('<code></code>');
          preCod = $('<pre></pre>');
          splData = dataIn.split("\n");
          for (line in splData){
              preCod.append('<div class="row model-row">' + escapeHtml(splData[line]) + '</div>');
          }
          modCod.append(preCod);
          saveObj.append(modCod);
    }

        function defineSites(data, definehosts=true) {
            sitesTab = $('<ul class="nav nav-pills" id="myTab" role="tablist"></ul>');
            allSites = $('<div id="sites" class="tab-content"></div>');
            for (i=0; i < data['general']['sites'].length; i++){
                sitename = data['general']['sites'][i];
                nName = sitename;
                // FE Config
                sitesTab.append('<li class="nav-item" role="presentation"><a class="nav-link" data-toggle="tab" aria-controls="'+ nName +'" aria-selected="false" id="tab_fe_'+ nName +'"  href="#view_fe_'+ nName +'">' + nName + ' FE</a></li>');
                allSites.append('<div class="tab-pane fade" role="tabpanel" aria-labelledby="tab_fe_'+ nName +'" id="view_fe_'+ nName +'"></div>');
                // All DTNs
                if (definehosts){
                  for (j=0; j < data['hostinfo'][sitename].length; j++){
                      dtns = data['hostinfo'][sitename][j];
                      htmlhostname = dtns['hostname'].replace(/\./g,'_');
                      nName = sitename + "_" + htmlhostname;
                      sitesTab.append('<li class="nav-item" role="presentation"><a class="nav-link" data-toggle="tab" aria-controls="'+ nName +'" aria-selected="false" id="tab_'+ nName +'"  href="#view_'+ nName +'">' + dtns['hostname'] + '</a></li>');
                      allSites.append('<div class="tab-pane fade row" role="tabpanel" aria-labelledby="tab_' + nName + '" id="view_'+ nName +'"></div>');
                  }
                }
            }
            $("#sites_tab").append(sitesTab);
            $("#main_tab").append(allSites);
        }

        function dumpData(data, configLine) {
            if (Array.isArray(data)) {
                for (i=0; i < data.length; i++){
                    dumpData(data[i], configLine);
                }}
            else if ($.isPlainObject(data)) {
                for (var key in data){
                    configLine.append("<b>"+ key +":</b>  ");
                    dumpData(data[key], configLine);
                    configLine.append("</br>");
                }}
            else {
                configLine.append(data + " ");
            }
        }

        function defineHostButtons(data, sitename, hostname){
          htmlhostname = hostname.replace(/\./g,'_');
          controlRow = $('<div class="row">');
          // Add Remove button
          controlRow.append('<div><form onsubmit="deletehost(\''+ htmlhostname +'\');" id="del-'+ htmlhostname +'" name="del-'+ htmlhostname +'"><input id="host-'+htmlhostname+'" name="hostname" type="hidden" value="'+hostname+'"><input id="ip-'+htmlhostname+'" name="ip" type="hidden" value="'+data['ip']+'"><input id="sitename-'+htmlhostname+'" name="sitename" type="hidden" value="'+sitename+'"><input value="Delete Host" type="submit" class="btn btn-danger"></form></div>');
          return controlRow;
        }

        function defineDTNConfig(data, sitename, hostname) {
          htmlhostname = hostname.replace(/\./g,'_');
          menCol = $('<div class="nav flex-column nav-pills" id="v-pills-tab" role="tablist" aria-orientation="vertical"></div>');
          cntDiv = $('<div class="tab-content" id="v-pills-tabContent"></div>');
          for (var key in data['hostinfo']){
             if (key === 'Summary') {continue;}
             if ($.isPlainObject(data['hostinfo'][key])){
               menCol.append('<a class="nav-link" id="v-pills-'+ htmlhostname + '_' + key + '-tab" data-toggle="pill" href="#v-pills-'+ htmlhostname + '_' +key+'" role="tab" aria-controls="v-pills-'+ htmlhostname + '_' + key +'" aria-selected="true">'+ key +'</a>');
               cntDiv.append('<div class="tab-pane fade" id="v-pills-'+ htmlhostname + '_' +key+'" role="tabpanel" aria-labelledby="v-pills-'+ htmlhostname + '_' +key+'-tab"></div>');
             }
          }
          nRow = $('<div class="row">');
          menCol = $('<div class="col-3">').append(menCol);
          cntDiv = $('<div class="col-9">').append(cntDiv);
          nRow.append(menCol).append(cntDiv);
          $('#view_'+sitename+'_'+ htmlhostname ).append(nRow);

          for (var key in data['hostinfo']){
            sitesConfig = $('<table id="agent_'+ htmlhostname +'_'+ key +'" class="table"></table>');
            sitesConfig.append('<thead class="thead-dark"><tr><th scope="col">Parameter</th><th scope="col">Value</th></tr></thead>');
            for (var key1 in data['hostinfo'][key]) {
                line = $('<tr></tr>');
                configLine = $('<td></td>');
                line.append('<th scope="row">'+ key1 +'</th>');
                dumpData(data['hostinfo'][key][key1], configLine);
                line.append(configLine);
                sitesConfig.append(line);
            }
            $('#v-pills-' + htmlhostname + '_' +key).append(sitesConfig);
          };
        }

        function defineSitesConfig(data, sitename) {
          sitesConfig = $('<table id="viewtb_'+ sitename +'" class="table"></table>');
          sitesConfig.append('<thead class="thead-dark"><tr><th scope="col">Parameter</th><th scope="col">Value</th></tr></thead>');
          for (var key in data){
            if (key == 'hostinfo') {continue;}
            line = $('<tr></tr>');
            line.append('<th scope="row">'+ key +'</th>');
            configLine = $('<td></td>');
            dumpData(data[key], configLine);
            line.append(configLine);
            sitesConfig.append(line);
         }
        $('#view_fe_'+ sitename).append(sitesConfig);
        }

        function doSiteUpdate(ids) {
        strSite = document.getElementById(ids + "sitename").value;
        $.ajax({url: strSite + '/sitefe/json/frontend/getdata',
            dataType: 'json', data: "", async: false,
            success: function(json){
                for (j=0; j < json.length; j++){
                    addDropDown(json[j]['hostname'], $("#" + ids + "dtn"));
                }
            }
        });
        }

        function doDTNUpdate(ids) {
        strDTN = document.getElementById(ids + "dtn").value;
        strSite = document.getElementById(ids + "sitename").value;
        $.ajax({url: strSite + '/sitefe/json/frontend/getdata',
            dataType: 'json', data: "", async: false,
            success: function(json){
                for (j=0; j < json.length; j++){
                    if (strDTN == json[j]['hostname']) {
                        var myObject = (0, eval)('(' + json[j]['hostinfo'] + ')');
                        for (const [key, value] of Object.entries(myObject['NetInfo']['interfaces'])) {
                            if (! $.isEmptyObject(value['vlans'])) {
                              for (const [key1, value1] of Object.entries(value['vlans'])) {
                                if (value1['provisioned']) {
                                    addDropDown(key1, $("#" + ids + "interface"));
                                }
                              }
                            }
                        }
                    }
                }
            }
        });
      }

function addDropDown(dropdownVal, saveObj){
    saveObj.append('<option>'+dropdownVal+'</option>');
}

// Credit to: https://stackoverflow.com/questions/4810841/pretty-print-json-using-javascript
function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        var cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
}
