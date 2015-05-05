var express     = require('express');
var app         = express();
var fs          = require('fs');
var utils       = require('./modules/utils');

app.use(express.static('public'));
app.set('views', './views');
app.set('view engine', 'jade');

app.get('/', function (req, res) {
    res.render('index');
});

app.get('/stats', function(req,res){
    res.send({
        indexed_count: Object.keys(companies).length,
        cat_count: Object.keys(categories).length
    });
});

app.get('/companies', function(req, res) {
    var q = req.query.q;

    if(q.length < 1) {
        return res.send({error: 'Too few characters in query.'});
    }

    var _q = q.toLowerCase();
    var _keys = _q.split(' ');

    var r = [];
    for(var perm in companies) {
        var c = companies[perm];
        for(var i = 0; i < _keys.length; i++) {
            if (_keys[i].length > 2 && c.n.toLowerCase().indexOf(_keys[i]) > -1) {                
                r.push({n:c.n, p: perm, i:c.i, s: c.s});
            }            
        }        
    }

    r.sort(function(a,b) {
        var sa = utils.getKeywordMatchScore(a.n, _keys);
        var sb = utils.getKeywordMatchScore(b.n, _keys);

        sa += 10 * a.s;
        sb += 10 * b.s;

        if(sa > sb) {
            return -1;
        }
        else if(sa < sb) {
            return 1;
        }
        return 0;
    });

    res.send(r);
});

app.get('/meta', function(req, res) {
    res.send(companies[req.query.p]);
});

app.get('/profile', function(req, res) {
    var permalink = req.query.p;
    var retries = 4;
    var profileData;

    var profileFilePath = './data/comps/' + permalink + '.json';
    try {
        //Check if local copy of profile exists.
        var profileStats = fs.lstatSync(profileFilePath);
        profileData = fs.readFile(profileFilePath, 'utf8', function(err, data) {
            if(err) {
                return res.send({});
            }
            res.send(data);
        });
    }
    catch (e) {
        // If local copy of profile doesn't exist, get data using API.
        (function getData() {
            utils.getOrganizationData(permalink, function(data, resCode) {
                if(resCode !== 200 && --retries >= 0) {
                    return getData();
                }

                try{
                    var dataObject = JSON.parse(data);
                    profileData = utils.getOrganizationProfileFromData(dataObject);

                    var success = {}, max = 0;
                    utils.getCategoriesFromData(dataObject).forEach(function(cat) {
                        if(companies[permalink].c.indexOf(cat) < 0) return;
                        var tree = utils.readTree(cat);
                        var pred = utils.getPrediction(utils.getPredictionInput(companies[permalink], dataObject), tree);

                        var total = 0, score = 0;
                        for(var l in pred) {
                            total += pred[l];
                        }
                        if(pred["1"] !==undefined) {
                            score = 0.5 + companies[permalink].s * 0.5 * pred["1"]/total;
                        }
                        else {
                            score = companies[permalink].s * 0.5 * pred["0"]/total;
                        }
                        success[cat] = score.toPrecision(5);
                        if(score > max) {
                            max = score;
                        }
                    });

                    success["all"] = max;
                    profileData.success = success;

                    fs.writeFile(profileFilePath, JSON.stringify(profileData), function(err) {});
                    res.send(profileData);   
                }
                catch(e) {
                    res.send({});
                    console.log('Error getting data (' + resCode + ')', data.split('\n').slice(0,3), e.stack);
                }
                
            });
        })();        
    }
});

console.log('Loading data...');
var server, companies, categories;
if(!fs.existsSync('./data/comps')) {
    fs.mkdirSync('./data/comps');
}
fs.readFile('data/companies_index.json', function(err, data) {
    if(err) throw err;
    companies = JSON.parse(data);
    categories = JSON.parse(fs.readFileSync('./data/categories.json'));
    console.log(Object.keys(companies).length + ' indexed company profiles.');
    server = app.listen(3000, function () {
        var port = server.address().port;
        console.log('Listening at port', port);
    });
});