// SPDX-License-Identifier: GPL-3.0-only
// Original test adapter. All decoding, analysis and instruction emission are
// performed by unchanged pinned ReXGlue sources, not a parallel translator.
#include "codegen/binary_view.h"
#include "codegen/codegen_context.h"
#include "codegen/module_stub.h"
#include "codegen/template_registry.h"
#include "codegen/template_render.h"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <format>
#include <iostream>
#include <map>
#include <vector>
int main(int argc,char** argv) {
  try {
    if(argc!=4) throw std::runtime_error("binary, offset map, output required");
    std::ifstream bytes(argv[1],std::ios::binary);
    std::vector<u8> data((std::istreambuf_iterator<char>(bytes)),{});
    std::ifstream map_file(argv[2]);
    std::map<std::size_t,std::string> symbols;
    std::string offset,type,name;
    while(map_file>>offset>>type>>name) symbols.emplace(0x82010000+std::stoul(offset,nullptr,16),name);
    if(data.empty()||symbols.empty()) throw std::runtime_error("empty test binary/map");
    namespace cg=rex::codegen;
    cg::StubModule module;module.Load(0x82010000,data.data(),data.size());module.SetName("fixtures");
    cg::RecompilerConfig config;
    config.out_directory_path=argv[3];
    config.vector_math={cg::VectorMath::kExact,cg::VectorMath::kExact,cg::VectorMath::kExact,
      cg::VectorMath::kExact,cg::VectorMath::kExact,cg::VectorMath::kExact,
      cg::VectorMath::kExact,cg::VectorMath::kExact,cg::VectorMath::kExact};
    config.forward_stack_stores=false;
    config.ctr_as_local_variable=false;config.xer_as_local_variable=false;
    config.reserved_register_as_local_variable=false;config.cr_registers_as_local_variables=false;
    config.non_argument_registers_as_local_variables=false;config.non_volatile_registers_as_local_variables=false;
    auto ctx=cg::CodegenContext::Create(cg::BinaryView::FromModule(module),std::move(config));
    cg::AnalyzeTestBinary(ctx,"fixtures",symbols,0x82010000,data.data(),data.size());
    cg::EmitContext emit{ctx.GetBinary(),ctx.GetConfig(),ctx.graph,ctx.GetLimits(),0,nullptr};
    std::vector<const cg::FunctionNode*> functions;
    for(const auto& [address,node]:ctx.graph.GetFunctions()) functions.push_back(node.get());
    std::sort(functions.begin(),functions.end(),[](auto* a,auto* b){return a->GetBase()<b->GetBase();});
    nlohmann::json model;model["functions"]=nlohmann::json::array();std::string code;
    for(auto* fn:functions) {
      const auto emitted=fn->EmitCpp(emit);
      if(emitted.empty()) throw std::runtime_error("empty function emission");
      model["functions"].push_back({{"name",std::format("fixtures_{:X}",fn->GetBase())}});code+=emitted;
    }
    model["functions_code"]=code;
    model["image_base"]="82010000";model["image_size"]="100000";
    model["code_base"]="82010000";model["code_size"]="100000";
    cg::TemplateRegistry registry;
    for(const auto& [id,file]:std::map<std::string,std::string>{{"test/ppc_config_h","ppc_config.h"},{"test/ppc_test_functions_cpp","ppc_test_functions.cpp"}}) {
      std::ofstream stream(std::filesystem::path(argv[3])/file);
      stream<<cg::RenderWithJSON(registry,id,model);
      if(!stream) throw std::runtime_error("cannot write emitted output");
    }
    std::cout<<"PPC_GENERATOR_PASS functions="<<functions.size()<<std::endl;
    return 0;
  } catch(const std::exception& e) {std::cerr<<"PPC_GENERATOR_ERROR: "<<e.what()<<std::endl;return 2;}
}
