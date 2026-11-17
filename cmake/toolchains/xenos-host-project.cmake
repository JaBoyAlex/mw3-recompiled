# Configure the shader tool against a separately hash-verified Microsoft DXC package.
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT TARGET Microsoft::DirectXShaderCompiler)
  if(NOT MW3_DXC_ROOT)
    message(FATAL_ERROR "MW3_DXC_ROOT must identify the verified DXC package")
  endif()
  add_library(Microsoft::DirectXShaderCompiler SHARED IMPORTED GLOBAL)
  if(WIN32)
    set_target_properties(Microsoft::DirectXShaderCompiler PROPERTIES
      IMPORTED_LOCATION "${MW3_DXC_ROOT}/bin/x64/dxcompiler.dll"
      IMPORTED_IMPLIB "${MW3_DXC_ROOT}/lib/x64/dxcompiler.lib"
      INTERFACE_INCLUDE_DIRECTORIES "${MW3_DXC_ROOT}/inc")
    add_library(Microsoft::DXIL SHARED IMPORTED GLOBAL)
    set_target_properties(Microsoft::DXIL PROPERTIES
      IMPORTED_LOCATION "${MW3_DXC_ROOT}/bin/x64/dxil.dll"
      IMPORTED_IMPLIB "${MW3_DXC_ROOT}/lib/x64/dxcompiler.lib")
  else()
    set_target_properties(Microsoft::DirectXShaderCompiler PROPERTIES
      IMPORTED_LOCATION "${MW3_DXC_ROOT}/lib/libdxcompiler.so"
      INTERFACE_INCLUDE_DIRECTORIES "${MW3_DXC_ROOT}/include/dxc")
  endif()
endif()
