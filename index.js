var express     = require('express');
var app         = express();
var fs          = require('fs');
var utils       = require('./modules/utils');
var d3          = require('d3');
var bodyParser  = require('body-parser');
var Heap        = require('heap');

app.use(express.static('public'));
app.use(bodyParser.json());
app.set('views', './views');
app.set('view engine', 'jade');

app.get('/', function (req, res) {
    res.render('index');
});


var tickerRaters = (function(){
    return {
        isAllStar: function(profile){
            return (profile.is_acquired || profile.num_acquisitions > 0) && profile.success.all >= 0.85;
        },

        isHot: function(profile) {
            var stdDivider = 3;
            if(!(profile.is_acquired || profile.num_acquisitions > 0)){
                if(profile.age < 42) {
                    if(profile.success.all < 0.15) {
                        if(profile.rate >= stdDivider) return true;
                    }
                    else {
                        if(profile.rate >= -stdDivider) return true;
                    }
                }
                else {
                    if(profile.success.all >= 0.15 && profile.success.all < 0.5){
                        if(profile.rate >= stdDivider) return true;
                    }
                    else if(profile.success.all >= 0.5){
                        if(profile.rate >= -stdDivider) return true;    
                    }
                }
            }
            return false;
        }
    };
})();

app.get('/stats', function(req,res){
    var trend_allstar = [], trend_hot = [];
    profileCache.savedProfiles().forEach(function(p){
        var profile = profileCache.getProfile(p);
        var meta = companies[p];
        meta.p = p;
        meta.s = profile.success.all;
        if(tickerRaters.isAllStar(profile)) {
            trend_allstar.push(meta);
        }
        if(tickerRaters.isHot(profile)) {
            trend_hot.push(meta);
        }
    });

    trend_allstar.sort(function(a,b){
        return b.s - a.s;
    });
    trend_hot.sort(function(a,b){
        return b.s - a.s;
    });

    console.log(trend_allstar, trend_hot);
    res.send({
        trends: {
            allstar: trend_allstar,
            hot: trend_hot
        },
        indexed_count: Object.keys(companies).length,
        cat_count: Object.keys(categories).length
    });
});

app.get('/companies', function(req, res) {
    var q = req.query.q;
    if(!q || q.length < 1) {
        return res.send({error: 'Too few characters in query.'});
    }

    var _q = q.toLowerCase();
    var _keys = _q.split(' ');

    var r = [], matched={};
    for(var perm in companies) {
        var c = companies[perm];
        for(var i = 0; i < _keys.length; i++) {
            if (_keys[i].length > 2 && !matched[perm] && c.n.toLowerCase().indexOf(_keys[i]) > -1) {                
                r.push({n:c.n, p: perm, i:c.i, s: c.s});
                matched[perm] = true;
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

app.post('/related', function(req, res) {
    var list = req.body;
    var result = [], competitors = [], catMap = {};
    list.forEach(function(c){
        if(profileCache.hasProfile(c)) {
            var profile = profileCache.getProfile(c);
            profile.competitors.forEach(function(competitor){
                if(competitor in companies && list.indexOf(competitor) === -1) {
                    var companyProfile = JSON.parse(JSON.stringify(companies[competitor]));
                    companyProfile.p = competitor;
                    competitors.push(companyProfile);
                    list.push(competitor);
                }
            });
        }

        companies[c].c.forEach(function(category) {
            if(!(category in catMap)){
                if(!ranker.has(category)) {
                    ranker.add(category);
                }
                ranker.getNLargest(category, 10).forEach(function(company) {
                    if(list.indexOf(company.p) === -1 && competitors.indexOf(company.p) === -1){
                        var companyProfile = JSON.parse(JSON.stringify(companies[company.p]));
                        companyProfile.p = company.p;
                        result.push(companyProfile); 
                        list.push(company.p);                           
                    }
                });
                catMap[category] = true;
            }
        });
    });

    function relatedSort(a, b) {
        var aScore = a.s;
        var bScore = b.s;
        if(profileCache.hasProfile(a.p)) {
            aScore = profileCache.getProfile(a.p).success.all;
        }
        if(profileCache.hasProfile(b.p)) {
            bScore = profileCache.getProfile(b.p).success.all;
        }

        return bScore - aScore;
    }

    competitors.sort(relatedSort);
    result.sort(relatedSort);

    var competitorsCount = Math.min(5, competitors.length);
    competitors = competitors.slice(0, competitorsCount);
    result = result.slice(0, 11 - competitorsCount);
    res.send(competitors.concat(result));
});

app.get('/competitors', function(req, res) {
    var permalink = req.query.p;
    if(!profileCache.hasProfile(permalink)) {
        return res.send(null);
    }

    var profile = profileCache.getProfile(permalink);
    var competitors = [];
    profile.competitors.forEach(function(c) {
        if(!companies[c]) return;
        var meta = JSON.parse(JSON.stringify(companies[c]));
        meta.p = c;
        competitors.push(meta);
    });
    competitors.sort(function(a, b) {
        return b.s - a.s;
    });

    var rank = 1, i = 0;
    while(competitors[i] && companies[permalink].s < competitors[i++].s) {
        rank++;
    }

    res.send({r: rank, t: competitors.length + 1, c: competitors});
});

app.get('/meta', function(req, res) {
    res.send(companies[req.query.p]);
});

function calcSuccessScores(permalink, data) {
    var success = {}, max = 0;
    utils.getCategoriesFromData(data).forEach(function(cat) {
        if(companies[permalink].c.indexOf(cat) < 0) return;
        var tree = utils.readTree(cat);
        var pred = utils.getPrediction(utils.getPredictionInput(companies[permalink], data), tree);

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
    success.all = max;
    return success;
}


var ranker = (function() {

    function heapCmpFunction(a, b){
        return a.s - b.s;
    }
    var MAX_HEAP_LENGTH = 10;
    var FILE_PATH = './data/ranks.json';
    var heaps = {};

    function setupRanksForCateory(category) {
        console.log("Ranking profiles for category " + category + "...");
        for(var company in companies) {
            if(companies[company].c && companies[company].c.indexOf(category) > -1) {
                var score;
                if(profileCache.hasProfile(company)) {
                    var profile = profileCache.getProfile(company);
                    score = profile.success[category];
                }
                else {
                    score = companies[company].s;
                }

                if(heaps[category].size() < MAX_HEAP_LENGTH) {
                    heaps[category].push({p: company, s: score});    
                }
                else {
                    updateRank(category, company, score, true); 
                }                
            }
        }
        saveToFile();
    }

    function addCategory(category) {
        if(hasCategory(category)) return;

        heaps[category] = new Heap(heapCmpFunction);
        setupRanksForCateory(category);
    }

    function hasCategory(category) {
        return category in heaps;
    }

    function setupAllRanks() {
        if(loadFromFile()) {
            return;
        }
        addCategory("Health and Wellness");
        addCategory("Software");
        addCategory("Biotechnology");
    }

    function updateRank(category, permalink, score, dontSave) {
        if(!hasCategory(category)) return;

        var index = heaps[category].toArray().map(function(x){ return x.p; }).indexOf(permalink);
        if( index > -1 ){
            heaps[category].nodes[index].s = score;
            heaps[category].heapify();
            if(!dontSave) 
                saveToFile();
        }
        else if(score > heaps[category].peek().s) {
            heaps[category].replace({p: permalink, s: score});
            if(!dontSave) 
                saveToFile();
        }
    }

    function exportObject() {
        var result = {};
        for(var category in heaps) {
            result[category] = heaps[category].toArray();
        }
        return result;
    }

    function importJSON(json) {
        var object = JSON.parse(json);
        heaps = {};
        for(var category in object) {
            heaps[category] = new Heap(heapCmpFunction);
            object[category].forEach(function(company) {
                heaps[category].push(company);
            });
        }
    }

    function saveToFile() {
        try {
            fs.writeFile(FILE_PATH, JSON.stringify(exportObject()), function(err) {
                if(err) throw err;
            });
        }
        catch(e){
            return false;
        }
        return true;
    }

    function loadFromFile() {
        try{
            var json = fs.readFileSync(FILE_PATH, 'utf8');
            importJSON(json);
        }
        catch(e) {
            return false;
        }
        return true;        
    }

    function getNLargest(category, n) {
        return Heap.nlargest(heaps[category].toArray(), n, heapCmpFunction);
    }

    return {
        init: setupAllRanks,
        add: addCategory,
        has: hasCategory,
        update: updateRank,
        getNLargest: getNLargest
    };
})();

var profileCache = (function() {
    var profiles = {};
    var PROFILE_DIR = './data/profiles/';

    var memcache = (function(){
        var map = {};
        var queue = [];
        var MAX_SIZE = 10;

        function has(id) {
            return id in map;
        }

        function save(id, d) {
            if(queue.length > MAX_SIZE) {
                var first = queue.shift();
                delete map[first];
            }
            queue.push(id);
            map[id] = d;
        }

        function get(id) {
            var index = queue.indexOf(id);
            if(index > -1) {
                queue.slice(index, 1);
                queue.push(id);
            }
            return map[id];
        }

        return {
            has: has,
            save: save,
            get: get
        };
    })();

    function readCachedProfilesToIndex() {
        var files = fs.readdirSync(PROFILE_DIR);
        files.forEach(function(f) {
            var permalink = f.split(".json")[0];
            profiles[permalink] = '';
        });
    }

    function isProfileInCache(permalink) {
        return permalink in profiles;
    }

    function readProfileFromCache(permalink) {
        try {
            if(memcache.has(permalink)) {
                return memcache.get(permalink);
            }
            var profile = JSON.parse(fs.readFileSync(PROFILE_DIR + permalink + ".json", "utf8"));
            memcache.save(permalink, profile);
            return profile;
        }
        catch(e) {
            return null;
        }
    }

    function saveProfileToCache(permalink, callback){
        var retries = 4;
        (function getData() {
            utils.getOrganizationData(permalink, function(data, resCode) {
                if(resCode !== 200 && --retries >= 0) {
                    return getData();
                }

                try{
                    var orgData = JSON.parse(data);
                    profileData = utils.getOrganizationProfileFromData(orgData);
                    profileData.success = calcSuccessScores(permalink, orgData);             
                    fs.writeFile(PROFILE_DIR + permalink + ".json", JSON.stringify(profileData), function(err) {
                        if(err){
                            console.error(err.message);
                        }
                        profiles[permalink] = '';
                        memcache.save(permalink, profileData);
                        companies[permalink].c.forEach(function(category) {
                            ranker.update(category, permalink, profileData.success.all);
                        });
                    });
                    callback(profileData); 
                }
                catch(e) {
                    if(--retries >= 0) {
                        return getData();
                    }
                    console.log('Error getting data (' + resCode + ')', data.split('\n').slice(0,3), e.stack);
                    callback(null);
                }
            });
        })(); 
    }

    function savedProfiles(){
        return Object.keys(profiles);
    }

    return {
        init: readCachedProfilesToIndex,
        getProfile: readProfileFromCache,
        hasProfile: isProfileInCache,
        saveProfile: saveProfileToCache,
        savedProfiles: savedProfiles
    };
})();

function getRateFromProfile(profile, avg) {
    var offsettedAge = Math.max(profile.age - 6, 1);
    var diff = profile.total_funding/offsettedAge - avg.r;
    return Math.round(diff / avg.d);    
}

app.get('/profile', function(req, res) {
    var permalink = req.query.p;

    if(!profileCache.hasProfile(permalink)) {
        profileCache.saveProfile(permalink, function(profile) {
            if(profile.total_funding && profile.age){
                var category = companies[permalink].c[companies[permalink].c.length - 1];
                var categoryInfo = categories[category];
                profile.rate = getRateFromProfile(profile, categoryInfo);
            }
            res.send(profile);
        });
        return;
    }
    var profile = profileCache.getProfile(permalink);
    res.send(profile);
});

console.log('Loading data...');
var server, companies, categories;
if(!fs.existsSync('./data/profiles')) fs.mkdirSync('./data/profiles');

fs.readFile('data/companies_index.json', function(err, data) {
    if(err) throw err;

    companies = JSON.parse(data);
    categories = JSON.parse(fs.readFileSync('./data/categories_freq.json'));
    profileCache.init();
    ranker.init();
    console.log(Object.keys(companies).length + ' indexed company profiles.');

    server = app.listen(3000, function () {
        var port = server.address().port;
        console.log('Listening at port', port);
    });
});