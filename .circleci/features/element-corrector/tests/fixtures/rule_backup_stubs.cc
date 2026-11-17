// Narrow test APIs, not a replacement for Chromium native tests.
#include <cassert>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>
#include <variant>
#include <utility>
template<class T> using raw_ptr=T*;
namespace base {
class DictValue;class ListValue;
class Value {
 public:
 using Data=std::variant<int,bool,std::string,std::shared_ptr<DictValue>,std::shared_ptr<ListValue>>;
 Data data=0;
 Value()=default;Value(int v):data(v){}Value(bool v):data(v){}Value(const std::string& v):data(v){}Value(const char* v):data(std::string(v)){}
 Value(DictValue v);Value(ListValue v);
 const DictValue* GetIfDict()const;const ListValue* GetIfList()const;
 const std::string* GetIfString()const{return std::get_if<std::string>(&data);}
 const DictValue& GetDict()const{return *GetIfDict();}
 const ListValue& GetList()const{return *GetIfList();}
 Value Clone()const;bool operator==(const Value& v)const;
};
class ListValue:public std::vector<Value>{public:void Append(Value v){push_back(std::move(v));}ListValue Clone()const{ListValue v;for(auto& x:*this)v.Append(x.Clone());return v;}};
class DictValue:public std::map<std::string,Value>{public:
 using Storage=std::map<std::string,Value>;
 // Chromium DictValue dereferences to a temporary pair of references.
 template<class Iter,class T> struct ProxyIterator {
   Iter iterator;
   using reference=std::pair<const std::string&,T&>;
   reference operator*()const{return {iterator->first,iterator->second};}
   ProxyIterator& operator++(){++iterator;return *this;}
   bool operator!=(const ProxyIterator& other)const{return iterator!=other.iterator;}
 };
 auto begin(){return ProxyIterator<Storage::iterator,Value>{Storage::begin()};}
 auto end(){return ProxyIterator<Storage::iterator,Value>{Storage::end()};}
 auto begin()const{return ProxyIterator<Storage::const_iterator,const Value>{Storage::begin()};}
 auto end()const{return ProxyIterator<Storage::const_iterator,const Value>{Storage::end()};}
 void Set(const std::string& k,Value v){insert_or_assign(k,std::move(v));}
 const Value* Find(const std::string& k)const{auto it=find(k);return it==Storage::end()?nullptr:&it->second;}
 const DictValue* FindDict(const std::string& k)const{auto* v=Find(k);return v?v->GetIfDict():nullptr;}
 const ListValue* FindList(const std::string& k)const{auto* v=Find(k);return v?v->GetIfList():nullptr;}
 ListValue* FindList(const std::string& k){return const_cast<ListValue*>(std::as_const(*this).FindList(k));}
 const std::string* FindString(const std::string& k)const{auto* v=Find(k);return v?v->GetIfString():nullptr;}
 std::optional<int> FindInt(const std::string& k)const{auto* v=Find(k);if(v)if(auto* n=std::get_if<int>(&v->data))return *n;return {};}
 bool FindBool(const std::string& k)const{return std::get<bool>(Find(k)->data);}
 void Remove(const std::string& k){erase(k);}
 DictValue Clone()const{DictValue v;for(auto [k,x]:*this)v.Set(k,x.Clone());return v;}
};
Value::Value(DictValue v):data(std::make_shared<DictValue>(std::move(v))){}
Value::Value(ListValue v):data(std::make_shared<ListValue>(std::move(v))){}
const DictValue* Value::GetIfDict()const{auto* v=std::get_if<std::shared_ptr<DictValue>>(&data);return v?v->get():nullptr;}
const ListValue* Value::GetIfList()const{auto* v=std::get_if<std::shared_ptr<ListValue>>(&data);return v?v->get():nullptr;}
Value Value::Clone()const{if(auto* v=GetIfDict())return v->Clone();if(auto* v=GetIfList())return v->Clone();return *this;}
bool Value::operator==(const Value& v)const{if(auto* d=GetIfDict())return v.GetIfDict()&&*d==v.GetDict();if(auto* l=GetIfList())return v.GetIfList()&&*l==v.GetList();return data==v.data;}
class SupportsUserData{public:class Data{public:virtual ~Data()=default;};};
// Parser fixtures only: parser itself is covered by pinned-header compile checks.
std::map<std::string,DictValue> inputs;
constexpr int JSON_PARSE_RFC=0;
class JSONReader{public:static std::optional<DictValue> ReadDict(const std::string& s,int){auto it=inputs.find(s);if(it==inputs.end())return {};return it->second.Clone();}};
std::string dump(const Value& v){if(auto* d=v.GetIfDict()){std::string s="{";for(auto [k,x]:*d)s+=k+dump(x);return s+"}";}if(auto* l=v.GetIfList()){std::string s="[";for(auto& x:*l)s+=dump(x);return s+"]";}if(auto* s=v.GetIfString())return *s;if(auto* i=std::get_if<int>(&v.data))return std::to_string(*i);return std::get<bool>(v.data)?"true":"false";}
std::optional<std::string> WriteJson(const DictValue& v){return dump(Value(v));}
}
class GURL{public:std::string s;explicit GURL(std::string v):s(std::move(v)){}bool SchemeIsHTTPOrHTTPS()const{return s.starts_with("https://")||s.starts_with("http://");}};
namespace url{class Origin{std::string s;public:static Origin Create(GURL u){Origin o;auto off=u.s.find("://");if(off!=std::string::npos){auto end=u.s.find_first_of("/?#",off+3);o.s=u.s.substr(0,end);}return o;}bool opaque()const{return s.empty();}GURL GetURL()const{return GURL(s);}std::string Serialize()const{return s;}};}
class PrefRegistrySimple{public:void RegisterDictionaryPref(const char*){}};
class PrefService{public:base::DictValue value;int writes=0,commits=0;const base::DictValue& GetDict(const char*)const{return value;}void SetDict(const char*,base::DictValue v){value=std::move(v);++writes;}void CommitPendingWrite(){++commits;}void ClearPref(const char*){value.clear();}};
class ScopedDictPrefUpdate{PrefService* p;public:ScopedDictPrefUpdate(PrefService* v,const char*):p(v){}base::DictValue* operator->(){return &p->value;}};
class Profile{public:std::unique_ptr<base::SupportsUserData::Data> data;PrefService prefs;PrefService* GetPrefs(){return &prefs;}bool IsOffTheRecord(){return false;}base::SupportsUserData::Data* GetUserData(const char*){return data.get();}void SetUserData(const char*,std::unique_ptr<base::SupportsUserData::Data> d){data=std::move(d);}};
// PRODUCTION_STORE_HERE
base::DictValue rule(std::string id,int rgb=0){base::DictValue r;r.Set("id",id);r.Set("tag","div");r.Set("role","");r.Set("property",0);r.Set("rgb",rgb);r.Set("ancestors",base::ListValue());return r;}
base::DictValue site(std::string origin,base::DictValue r){base::ListValue l;l.Append(std::move(r));base::DictValue d;d.Set(origin,std::move(l));return d;}
int main(){
 PrefService prefs;sandium::ElementColorRuleStore store(&prefs,false);
 base::inputs["one"]=site("https://example.com",rule("x"));
 auto result=store.ImportRules("one",false);assert(result.FindBool("ok")&&result.FindInt("added")==1);assert(prefs.writes==0&&prefs.value.empty());
 result=store.ImportRules("one",true);assert(result.FindBool("ok")&&prefs.writes==1&&prefs.commits==1);
 auto before=prefs.value.Clone();
 result=store.ImportRules("one",true);assert(result.FindInt("duplicates")==1&&result.FindInt("added")==0&&prefs.writes==1);
 base::inputs["conflict"]=site("https://example.com",rule("x",123));
 result=store.ImportRules("conflict",true);assert(result.FindInt("conflicts")==1&&prefs.value==before&&prefs.writes==1);
 base::inputs["path"]=site("https://example.com/path",rule("x"));
 assert(!store.ImportRules("path",true).FindBool("ok")&&prefs.value==before);
 base::inputs["bad"]=site("https://example.com",rule("x"));base::inputs["bad"].FindList("https://example.com")->Append(5);
 assert(!store.ImportRules("bad",true).FindBool("ok")&&prefs.value==before);
 assert(!store.ImportRules("unknown",true).FindBool("ok"));assert(!store.ImportRules(std::string(8*1024*1024+1,'x'),true).FindBool("ok"));
 // Multi-site overflow must not partly commit the first new site.
 base::DictValue many;for(int i=0;i<128;++i)many.Set("https://s"+std::to_string(i)+".test",base::ListValue());prefs.value=many.Clone();before=prefs.value.Clone();
 base::inputs["overflow"]=site("https://extra.test",rule("new"));assert(!store.ImportRules("overflow",true).FindBool("ok")&&prefs.value==before);
 base::ListValue full;for(int i=0;i<32;++i)full.Append(rule("r"+std::to_string(i)));prefs.value.clear();prefs.value.Set("https://example.com",full.Clone());before=prefs.value.Clone();
 base::inputs["multi"]=site("https://aaa.test",rule("first"));base::inputs["multi"].Set("https://example.com",base::inputs["one"].Find("https://example.com")->Clone());
 assert(!store.ImportRules("multi",true).FindBool("ok")&&prefs.value==before);
 // Replacing a full-list target is a retained conflict, not an overflow.
 base::inputs["full_conflict"]=site("https://example.com",rule("r0",123));assert(store.ImportRules("full_conflict",true).FindBool("ok")&&prefs.value==before);
 sandium::ElementColorRuleStore private_store(&prefs,true);assert(private_store.ExportRules().empty());assert(!private_store.ImportRules("one",true).FindBool("ok")&&prefs.value==before);
 assert(!store.ExportRules().empty());prefs.value.Set("https://bad.test",5);before=prefs.value.Clone();assert(store.ExportRules().empty());assert(!store.ImportRules("one",true).FindBool("ok")&&prefs.value==before);
 // No prefs and empty imports do not mutate storage.
 sandium::ElementColorRuleStore absent(nullptr,false);assert(absent.ExportRules().empty());assert(!absent.ImportRules("one",true).FindBool("ok"));
 prefs.value.clear();base::inputs["empty"]=base::DictValue();assert(store.ImportRules("empty",true).FindBool("ok")&&prefs.value.empty());
}
